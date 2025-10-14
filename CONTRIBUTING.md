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


## Tooling versions (reference)

- Python: 3.11
- Slither: 0.11.x  (e.g., `pipx install slither-analyzer==0.11.6`)
- Mythril: 0.25.x  (e.g., `pipx install mythril==0.25.5`)
- Node (optional): 18.x LTS

> CI does not install Slither/Mythril; tests mock their output. Use the versions above locally for consistent results.
