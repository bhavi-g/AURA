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
```

## Tooling versions (reference)

- Python: 3.11
- Slither: 0.11.x  (e.g., `pipx install slither-analyzer==0.11.6`)
- Mythril: 0.25.x  (e.g., `pipx install mythril==0.25.5`)
- Node (optional): 18.x LTS

> CI does not install Slither/Mythril; tests mock their output. Use the versions above locally for consistent results.

## Releasing

Releases publish `aura-audit` to PyPI via `.github/workflows/release.yml`,
triggered by pushing a `v*` tag. The version is derived from the tag itself
(`setuptools_scm`) — there's no version number to edit anywhere. See ADR
[0005](docs/adr/0005-dynamic-versioning-trusted-publishing.md) for why.

**One-time setup per PyPI project** (already done for `aura-audit` — needed
again only if the project is ever recreated, or for a new package):
1. Create a PyPI account if you don't have one, with 2FA enabled.
2. On https://pypi.org/manage/account/publishing/, register a "pending
   trusted publisher" (the project doesn't need to exist yet):
   - PyPI project name: `aura-audit`
   - Owner: `bhavi-g` · Repository: `AURA` · Workflow filename: `release.yml`
   - Environment name: `pypi`
3. In the GitHub repo → Settings → Environments, create an environment
   named `pypi` (matches `release.yml`'s `environment: pypi`).

**To cut a release:**
```bash
git checkout main && git pull
git tag vX.Y.Z
git push origin vX.Y.Z
```
Watch the Actions tab for the `release` workflow. It builds the sdist/wheel,
then publishes to PyPI with no stored token (OIDC trusted publishing).
PyPI versions are immutable once published — double-check `main` is what
you want released before pushing the tag.
