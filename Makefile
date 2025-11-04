# =========================================================
# AURA Project Makefile — Week 4 (Evaluation + QoL)
# =========================================================

.DEFAULT_GOAL := week3
.PHONY: test format analyze report smoke week3 eval bench

# Run all tests quietly (no warnings)
test:
	pytest -q --disable-warnings

# Auto-format and lint everything
format:
	pre-commit run -a || true

# Core analyzer
analyze:
	python -m aura analyze samples/contracts -p week3-smoke

# Post-processing Markdown + SARIF report
report:
	python tools/post_analyze.py

# Quick preview of first 40 lines of Markdown report
smoke: analyze report
	sed -n '1,40p' reports/index.md

# Full week-3 workflow: lint + test + smoke
week3: format test smoke

# Week-4 evaluation (uses default paths set in CLI)
eval:
	python -m aura eval

# Combined bench run (analyze + eval + show metrics)
bench:
	$(MAKE) analyze
	$(MAKE) eval
	@echo "---- metrics.json ----"
	@cat reports/metrics.json
