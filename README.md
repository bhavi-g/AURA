# AURA — Phase 0

Bootstrap monorepo with Python CLI, tests, linting, pre-commit, and CI.

## Quickstart
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install
python aura.py hello --name AURA
pytest -q
