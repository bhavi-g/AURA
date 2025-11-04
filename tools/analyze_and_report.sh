#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-samples/contracts}"
PROJECT="${2:-week3-smoke}"

python -m aura analyze "$TARGET" -p "$PROJECT"
python tools/post_analyze.py

echo
echo "Artifacts:"
ls -lh reports/index.md reports/summary.json reports/summary.sarif reports/slither_parsed.json
