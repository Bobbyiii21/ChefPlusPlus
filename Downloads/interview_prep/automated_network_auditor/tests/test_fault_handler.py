"""
Tests for fault_handler — retry decorator and CircuitBreaker.
"""
import time
import pytest
from unittest.mock import MagicMock, patch, call

from auditor.fault_handler import retry_with_backoff, CircuitBreaker, CircuitState


# ── retry_with_backoff ────────────────────────────────────────────────────────

class TestRetryWithBackoff:

    def test_success_on_first_try(self):
        mock_fn = MagicMock(return_value="ok")

        @retry_with_backoff(retries=3, base_delay=0.01)
        def fn():
            return mock_fn()

        result = fn()
        assert result == "ok"
        assert mock_fn.call_count == 1

    def test_success_after_retries(self):
        mock_fn = MagicMock(side_effect=[OSError("timeout"), OSError("timeout"), "recovered"])

        @retry_with_backoff(retries=2, base_delay=0.01, exceptions=(OSError,))
        def fn():
            return mock_fn()

        result = fn()
        assert result == "recovered"
        assert mock_fn.call_count == 3

    def test_raises_after_exhausting_retries(self):
        mock_fn = MagicMock(side_effect=ConnectionError("unreachable"))

        @retry_with_backoff(retries=2, base_delay=0.01, exceptions=(ConnectionError,))
        def fn():
            return mock_fn()

        with pytest.raises(RuntimeError, match="failed after 3 attempts"):
            fn()
        assert mock_fn.call_count == 3

    def test_does_not_retry_unmatched_exception(self):
        """Non-listed exception must propagate immediately without retry."""
        mock_fn = MagicMock(side_effect=ValueError("bad input"))

        @retry_with_backoff(retries=3, base_delay=0.01, exceptions=(OSError,))
        def fn():
            return mock_fn()

        with pytest.raises(ValueError):
            fn()
        assert mock_fn.call_count == 1

    def test_backoff_delay_increases(self):
        """Verify sleep is called with increasing delays."""
        calls = []

        @retry_with_backoff(retries=3, base_delay=1.0, backoff=2.0, exceptions=(OSError,))
        def fn():
            raise OSError("fail")

        with patch("auditor.fault_handler.time.sleep") as mock_sleep:
            with pytest.raises(RuntimeError):
                fn()

        delays = [c.args[0] for c in mock_sleep.call_args_list]
        assert delays == [1.0, 2.0, 4.0]

    def test_preserves_function_name(self):
        @retry_with_backoff()
        def my_function():
            return True

        assert my_function.__name__ == "my_function"


# ── CircuitBreaker ────────────────────────────────────────────────────────────

class TestCircuitBreaker:

    def test_closed_by_default(self):
        cb = CircuitBreaker()
        assert cb.allow_request("10.0.0.1") is True
        assert cb.state("10.0.0.1") == "CLOSED"

    def test_opens_after_threshold(self):
        cb = CircuitBreaker(failure_threshold=3, reset_timeout=60)
        host = "10.0.0.1"
        for _ in range(3):
            cb.record_failure(host)
        assert cb.state(host) == "OPEN"
        assert cb.allow_request(host) is False

    def test_stays_closed_below_threshold(self):
        cb = CircuitBreaker(failure_threshold=3)
        host = "10.0.0.2"
        cb.record_failure(host)
        cb.record_failure(host)
        assert cb.state(host) == "CLOSED"
        assert cb.allow_request(host) is True

    def test_transitions_open_to_half_open(self):
        cb = CircuitBreaker(failure_threshold=1, reset_timeout=0.05)
        host = "10.0.0.3"
        cb.record_failure(host)
        assert cb.state(host) == "OPEN"
        time.sleep(0.1)
        assert cb.allow_request(host) is True
        assert cb.state(host) == "HALF_OPEN"

    def test_success_in_half_open_closes_circuit(self):
        cb = CircuitBreaker(failure_threshold=1, reset_timeout=0.05)
        host = "10.0.0.4"
        cb.record_failure(host)
        time.sleep(0.1)
        cb.allow_request(host)  # transitions to HALF_OPEN
        cb.record_success(host)
        assert cb.state(host) == "CLOSED"
        assert cb.allow_request(host) is True

    def test_failure_in_half_open_reopens(self):
        cb = CircuitBreaker(failure_threshold=1, reset_timeout=0.05)
        host = "10.0.0.5"
        cb.record_failure(host)
        time.sleep(0.1)
        cb.allow_request(host)  # HALF_OPEN
        cb.record_failure(host)
        assert cb.state(host) == "OPEN"

    def test_success_resets_failure_counter(self):
        cb = CircuitBreaker(failure_threshold=3)
        host = "10.0.0.6"
        cb.record_failure(host)
        cb.record_failure(host)
        cb.record_success(host)
        assert cb.state(host) == "CLOSED"
        # Failures reset — need 3 new failures to open again
        cb.record_failure(host)
        cb.record_failure(host)
        assert cb.state(host) == "CLOSED"

    def test_reset_clears_all_state(self):
        cb = CircuitBreaker(failure_threshold=1)
        host = "10.0.0.7"
        cb.record_failure(host)
        assert cb.state(host) == "OPEN"
        cb.reset(host)
        assert cb.state(host) == "CLOSED"
        assert cb.allow_request(host) is True

    def test_independent_hosts(self):
        cb = CircuitBreaker(failure_threshold=2)
        cb.record_failure("10.0.0.1")
        cb.record_failure("10.0.0.1")  # OPEN
        assert cb.allow_request("10.0.0.1") is False
        assert cb.allow_request("10.0.0.2") is True  # different host unaffected

    def test_multiple_hosts_tracked_independently(self):
        cb = CircuitBreaker(failure_threshold=3)
        for i in range(3):
            cb.record_failure("bad_host")
        cb.record_failure("ok_host")

        assert cb.state("bad_host") == "OPEN"
        assert cb.state("ok_host") == "CLOSED"
