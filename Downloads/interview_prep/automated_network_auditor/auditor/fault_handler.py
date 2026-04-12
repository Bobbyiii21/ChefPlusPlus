"""
Fault Tolerance — Retry + Circuit Breaker
==========================================
retry_with_backoff  : exponential back-off decorator for transient errors.
CircuitBreaker      : per-host open/half-open/closed state machine that
                      prevents hammering unreachable devices.
"""
import time
import logging
import functools
from enum import Enum, auto
from typing import Callable, Type, Tuple, Any

logger = logging.getLogger(__name__)


# ─── Retry with Exponential Back-off ─────────────────────────────────────────

def retry_with_backoff(
    retries: int = 3,
    base_delay: float = 2.0,
    backoff: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
) -> Callable:
    """
    Decorator — retry *retries* times with exponential back-off.

    Args:
        retries:    Maximum number of attempts after initial failure.
        base_delay: Seconds to wait before the first retry.
        backoff:    Multiplier applied to delay on each subsequent retry.
        exceptions: Exception types that trigger a retry.

    Example::

        @retry_with_backoff(retries=3, base_delay=1.0, exceptions=(OSError,))
        def connect(host):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            delay = base_delay
            last_exc: Exception | None = None
            for attempt in range(retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    if attempt == retries:
                        break
                    logger.warning(
                        "%s attempt %d/%d failed (%s). Retrying in %.1fs …",
                        func.__name__, attempt + 1, retries + 1, exc, delay,
                    )
                    time.sleep(delay)
                    delay *= backoff
            raise RuntimeError(
                f"{func.__name__} failed after {retries + 1} attempts"
            ) from last_exc
        return wrapper
    return decorator


# ─── Circuit Breaker ─────────────────────────────────────────────────────────

class CircuitState(Enum):
    CLOSED = auto()      # Normal — requests pass through
    OPEN = auto()        # Fault threshold breached — requests blocked
    HALF_OPEN = auto()   # Probe attempt allowed


class CircuitBreaker:
    """
    Per-host circuit breaker.

    States:
      CLOSED    → normal operation; consecutive failures increment counter.
      OPEN      → all calls blocked; reopens after *reset_timeout* seconds.
      HALF_OPEN → one probe attempt; success resets to CLOSED, failure reopens.

    Args:
        failure_threshold: Consecutive failures before opening the circuit.
        reset_timeout:     Seconds the circuit stays OPEN before half-opening.

    Example::

        cb = CircuitBreaker(failure_threshold=3, reset_timeout=30)
        if cb.allow_request("10.0.0.1"):
            try:
                result = connect("10.0.0.1")
                cb.record_success("10.0.0.1")
            except Exception as e:
                cb.record_failure("10.0.0.1")
                raise
    """

    def __init__(self, failure_threshold: int = 3, reset_timeout: float = 30.0) -> None:
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        # Per-host state tracking
        self._failures: dict[str, int] = {}
        self._state: dict[str, CircuitState] = {}
        self._opened_at: dict[str, float] = {}

    # ── Public API ────────────────────────────────────────────────────────────

    def allow_request(self, host: str) -> bool:
        """Return True if the circuit allows a request to *host*."""
        state = self._state.get(host, CircuitState.CLOSED)

        if state == CircuitState.CLOSED:
            return True

        if state == CircuitState.OPEN:
            if time.monotonic() - self._opened_at.get(host, 0) >= self.reset_timeout:
                logger.info("Circuit for %s → HALF_OPEN (probe attempt)", host)
                self._state[host] = CircuitState.HALF_OPEN
                return True
            logger.warning("Circuit for %s is OPEN — request blocked.", host)
            return False

        # HALF_OPEN: allow exactly one probe
        return True

    def record_success(self, host: str) -> None:
        """Reset the circuit to CLOSED after a successful request."""
        if self._state.get(host) in (CircuitState.HALF_OPEN, CircuitState.OPEN):
            logger.info("Circuit for %s → CLOSED (recovered).", host)
        self._failures[host] = 0
        self._state[host] = CircuitState.CLOSED

    def record_failure(self, host: str) -> None:
        """Increment failure counter; open the circuit if threshold is reached."""
        self._failures[host] = self._failures.get(host, 0) + 1
        failures = self._failures[host]

        if self._state.get(host) == CircuitState.HALF_OPEN or failures >= self.failure_threshold:
            logger.error(
                "Circuit for %s → OPEN after %d failure(s).", host, failures
            )
            self._state[host] = CircuitState.OPEN
            self._opened_at[host] = time.monotonic()
        else:
            logger.warning(
                "Host %s failure %d/%d.", host, failures, self.failure_threshold
            )

    def state(self, host: str) -> str:
        return self._state.get(host, CircuitState.CLOSED).name

    def reset(self, host: str) -> None:
        """Manually reset circuit for *host*."""
        self._failures.pop(host, None)
        self._state.pop(host, None)
        self._opened_at.pop(host, None)


# Module-level shared circuit breaker (used by ssh_client)
_global_cb = CircuitBreaker(failure_threshold=3, reset_timeout=30.0)


def get_circuit_breaker() -> CircuitBreaker:
    return _global_cb
