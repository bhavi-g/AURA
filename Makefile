.PHONY: test format analyze report smoke week3
test:
\tpytest -q --disable-warnings

format:
\tpre-commit run -a || true

analyze:
\tpython -m aura analyze samples/contracts -p week3-smoke

report:
\tpython tools/post_analyze.py

smoke: analyze report
\t@sed -n '1,40p' reports/index.md

week3: format test smoke
