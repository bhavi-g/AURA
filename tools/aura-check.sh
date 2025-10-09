#!/usr/bin/env bash
set -euo pipefail
red() { printf "\033[31m%s\033[0m\n" "$*"; }
grn() { printf "\033[32m%s\033[0m\n" "$*"; }

python --version
if [ -f ".venv/bin/python" ]; then grn "venv present"; else red "venv missing (.venv)"; exit 1; fi

req=( "pyproject.toml" ".editorconfig" ".pre-commit-config.yaml" ".gitignore" ".github/workflows/ci.yml" "src/aura/__init__.py" "src/aura/cli.py" "tests/test_version.py" )
for f in "${req[@]}"; do [ -f "$f" ] || { red "missing $f"; exit 1; }; done
grn "required files present"

grep -q '^\[project\]' pyproject.toml || { red "pyproject missing [project]"; exit 1; }
grep -q '^\[project.scripts\]' pyproject.toml || { red "pyproject missing [project.scripts]"; exit 1; }
grep -q 'aura = "aura.cli:main"' pyproject.toml || { red "console script not set"; exit 1; }
grn "pyproject looks good"

python - <<'PY'
import re, aura
assert re.match(r"^\d+\.\d+\.\d+", getattr(aura, "__version__", "")), "__version__ invalid"
print("OK:", aura.__version__)
PY

for t in black ruff pytest pre-commit; do
  command -v "$t" >/dev/null || { red "tool not found: $t"; exit 1; }
  "$t" --version >/dev/null
done
grn "black/ruff/pytest/pre-commit available"

ruff check . --fix
ruff format --check .
black --check .
pytest -q
pre-commit run --all-files

git rev-parse --is-inside-work-tree >/dev/null 2>&1 || { red "not a git repo"; exit 1; }
clean=$(git status --porcelain)
if [ -z "$clean" ]; then grn "git working tree clean"; else red "uncommitted changes present"; echo "$clean"; exit 1; fi
origin=$(git remote get-url origin 2>/dev/null || true)
if [ -n "$origin" ]; then grn "origin set: $origin"; else red "git remote 'origin' not set"; exit 1; fi

grn "AURA health check passed"
