
# AURA – Hardening Pack (v2)
**Generated:** 2025-10-13T11:46:47.630339Z

This pack implements your code-quality, testing, performance, architecture, security, CI/CD, docs & polish steps.

## How to integrate
1. Merge these files into your existing repo (or unzip alongside the v1 Starter Kit).
2. Run `pre-commit install` and `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env` and set secrets.
4. `docker-compose up --build api` to run the API at http://localhost:8000.

## Highlights
- `pyproject.toml` (black, isort, ruff)
- `.pre-commit-config.yaml`
- `tests/` with FastAPI tests
- `docker-compose.yml` + `.env.example`
- Logging for API
- CI workflow for lint/type/test
- Templates: CONTRIBUTING, CHANGELOG, SECURITY, CODEOWNERS
- Mermaid architecture diagram in README


CI ping: Mon 13 Oct 2025 23:55:39 EDT

## Quickstart

Run analyzers and generate reports:
```bash
python -m aura analyze samples/contracts -p week3-smoke
python tools/post_analyze.py
