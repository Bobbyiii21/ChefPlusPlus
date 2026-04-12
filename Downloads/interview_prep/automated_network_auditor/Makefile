# =============================================================================
# Makefile — Automated Network Auditor
# =============================================================================
.PHONY: help install lint format typecheck test test-cov audit commission \
        inventory bash-lint clean

PYTHON  := python3
VENV    := .venv
PIP     := $(VENV)/bin/pip
PY      := $(VENV)/bin/python

# ── Help ──────────────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "  Automated Network Auditor — make targets"
	@echo "  ─────────────────────────────────────────────"
	@echo "  install     Install all dependencies into .venv"
	@echo "  lint        Run flake8 style check"
	@echo "  format      Run black formatter"
	@echo "  typecheck   Run mypy type check"
	@echo "  bash-lint   Run shellcheck on all Bash scripts"
	@echo "  test        Run pytest (simulate mode)"
	@echo "  test-cov    Run pytest with HTML coverage report"
	@echo "  audit       Run full simulated compliance audit"
	@echo "  commission  Dry-run commission for first device"
	@echo "  inventory   Show device inventory"
	@echo "  clean       Remove __pycache__, .mypy_cache, coverage"
	@echo ""

# ── Setup ─────────────────────────────────────────────────────────────────────
install:
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	@echo "✓ Dependencies installed. Activate with: source $(VENV)/bin/activate"

# ── Code quality ──────────────────────────────────────────────────────────────
lint:
	$(PY) -m flake8 auditor/ cli/ scripts/python/ tests/ \
		--max-line-length=100 --exclude=__pycache__,.venv

format:
	$(PY) -m black auditor/ cli/ scripts/python/ tests/

typecheck:
	$(PY) -m mypy auditor/ cli/ scripts/python/ --ignore-missing-imports

bash-lint:
	@if command -v shellcheck >/dev/null 2>&1; then \
		find scripts/bash -name "*.sh" | xargs shellcheck --severity=warning; \
		echo "✓ shellcheck passed."; \
	else \
		echo "WARNING: shellcheck not installed — skipping Bash lint."; \
	fi

# ── Tests ─────────────────────────────────────────────────────────────────────
test:
	$(PY) -m pytest tests/ -v --tb=short

test-cov:
	$(PY) -m pytest tests/ \
		--cov=auditor --cov=scripts/python \
		--cov-report=term-missing \
		--cov-report=html:htmlcov \
		--cov-fail-under=80 \
		-v
	@echo "✓ Coverage report: htmlcov/index.html"

# ── Audit ─────────────────────────────────────────────────────────────────────
audit:
	$(PY) -m cli.main audit --simulate

audit-json:
	$(PY) -m cli.main audit --simulate --no-detail --output audit_report.json
	@echo "✓ Report saved: audit_report.json"

# ── Commission ────────────────────────────────────────────────────────────────
commission:
	$(PY) scripts/python/commission.py

# ── Inventory ─────────────────────────────────────────────────────────────────
inventory:
	$(PY) -m cli.main inventory

# ── Clean ─────────────────────────────────────────────────────────────────────
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov"     -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	find . -name ".coverage" -delete 2>/dev/null || true
	find . -name "coverage.xml" -delete 2>/dev/null || true
	@echo "✓ Clean complete."
