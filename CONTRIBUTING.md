# Contributing to AURA

## Prereqs
- Python 3.11+
- macOS/Linux recommended
- `slither` and `mythril` optional for local runs (pipeline tests mock them)

## Setup
```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .[dev]
pre-commit install
