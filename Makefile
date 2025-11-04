.DEFAULT_GOAL := week3
.PHONY: test format analyze report smoke week3 eval

test: ; pytest -q --disable-warnings
format: ; pre-commit run -a || true
analyze: ; python -m aura analyze samples/contracts -p week3-smoke
report: ; python tools/post_analyze.py
smoke: analyze report ; sed -n '1,40p' reports/index.md
week3: format test smoke ;
eval: \tpython -m aura eval --golden reports/golden/summary.sarif --report reports/summary.sarif
