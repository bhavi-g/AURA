# Phase 3 — PyPI publish + install polish — Design

**Status:** approved
**Phase:** `docs/phases/phase-3.md`
**Date:** 2026-08-04

## Why

The #1 adoption blocker for an OSS CLI is install friction. `pipx install <package>`
should just work, prereqs should be documented and reproducible, and releases
should be automated rather than manual `twine upload`.

## Decisions

### 1. PyPI distribution name: `aura-audit`

`aura` is already registered on PyPI (an unrelated "Agentic TUI" project by a
different author). The importable Python package stays `aura`
(`src/aura/...`, `import aura`) and the CLI command stays `aura` — a
`[project.scripts]` entry point name is independent of the distribution name.
Only the string you pass to `pip install` / `pipx install` changes, to
`aura-audit`.

This means every place in the codebase that currently hardcodes the
*distribution* name `"aura"` (as opposed to the importable module name, which
is unaffected) must change to `"aura-audit"`:
- `src/aura/cli.py::version_cmd` — `metadata.version("aura")`
- `src/aura/cli.py::_version_callback` — `metadata.version("aura")`

### 2. Dynamic versioning via `setuptools_scm`

`pyproject.toml` currently hardcodes `version = "0.0.0"`, disconnected from
the real git tags already in the repo (latest: `v0.4.0`). Switch to:

```toml
[project]
dynamic = ["version"]

[tool.setuptools_scm]
fallback_version = "0.0.0"
```

with `setuptools_scm` added to `[build-system].requires`. The version is then
derived from the git tag at build/install time (tag `v0.5.0` → package
version `0.5.0`; commits after a tag get a PEP 440 dev suffix, e.g.
`0.5.1.dev3+g1a2b3c4`). `fallback_version` only covers builds where SCM
parsing fails entirely — i.e. no `.git` directory at all (a tarball) — so the
build doesn't hard-fail; it degrades to `0.0.0` instead. A shallow/tagless
clone (`.git` present, but no reachable tag) is a different case:
setuptools_scm still finds a `.git` directory, so it does *not* fall back —
it derives a fabricated version from the commit hash alone, e.g.
`0.0.1.dev1+g1a2b3c4`.

`src/aura/__init__.py` currently hardcodes `__version__ = "0.0.1"` (already
stale vs. the `v0.4.0` tag). Replace with a read of the installed
distribution's metadata, matching the pattern `cli.py` already uses:

```python
from importlib import metadata

try:
    __version__ = metadata.version("aura-audit")
except metadata.PackageNotFoundError:
    __version__ = "0.0.0.dev0"
```

No generated `_version.py` file — one source of truth (installed dist
metadata), consistent with how `cli.py` already reads the version.

**CI impact:** `.github/workflows/ci.yml`'s `actions/checkout@v4` step
currently defaults to a shallow clone (`fetch-depth: 1`, no tags), which
would make `setuptools_scm` unable to see any tag during the editable install
every CI job depends on (`pip install -e ".[dev]"`). Add
`fetch-depth: 0` there so tags are visible. (`fallback_version` is a safety
net for tarball-only builds, not a substitute for this — a shallow/tagless
checkout doesn't hit that fallback at all, it silently derives a fabricated
dev version like `0.0.1.dev1+g1a2b3c4` from the commit hash. We want CI to
reflect the real derived version, not a fabricated one.)

**Test impact:** `tests/test_phase0_cli.py::test_package_import_and_version`
asserts `re.match(r"^\d+\.\d+\.\d+", aura.__version__)`. Both a real
setuptools_scm-derived version (`0.4.1.dev3+g1a2b3c4`) and the fallback
(`0.0.0.dev0`) satisfy this. No test changes needed.

### 3. Packaging metadata

Add to `[project]` in `pyproject.toml`: `description`, `readme = "README.md"`,
`license`, `authors`, `classifiers` (`Programming Language :: Python :: 3.11`,
`License :: OSI Approved :: MIT License`, `Development Status :: 4 - Beta`,
`Environment :: Console`, `Topic :: Security`), and `project.urls`
(`Homepage`, `Repository`, `Issues` → `https://github.com/bhavi-g/AURA`).

Add a `LICENSE` file (MIT) at repo root — the README already states "MIT" in
its License section, but no `LICENSE` file exists in the repo. Needed for
PyPI's license classifier and GitHub's license detector to both work; this
completes an already-declared decision rather than making a new one.

### 4. Release automation: `.github/workflows/release.yml`

New workflow, triggered on pushing a `v*` tag:
- Checkout with `fetch-depth: 0` (tags must be visible for `setuptools_scm`).
- `python -m build` → sdist + wheel.
- Publish via **PyPI trusted publishing** (OIDC `id-token: write` permission,
  `pypa/gh-action-pypi-publish`) — no stored PyPI API token/secret in the repo.

Trusted publishing requires a one-time manual setup on pypi.org (outside this
repo, done by the human): create a PyPI account if needed, then register a
"pending trusted publisher" for the not-yet-published `aura-audit` project,
pointing at `bhavi-g/AURA`, workflow filename `release.yml`, and a `pypi`
GitHub Environment name. This implementation plan will include the exact
step-by-step instructions as a checklist at the point they're needed (before
the first real tag push) — the workflow code will be written and tested
(build step only, not an actual publish) before that point.

### 5. README

- Fix the stale "Python 3.10+" prerequisite (code has required `>=3.11` since
  before this session; README was never updated).
- Add `pipx install aura-audit` as the primary install path, ahead of the
  existing `poetry install` (kept, relabeled as the contributor/dev path).
- Document `solc` / `slither` setup reproducibly, matching what CI already
  does: `solc-select install <version>` / `solc-select use <version>`,
  `pipx install slither-analyzer`.
- Note explicitly that the installed command is still `aura` even though the
  package name is `aura-audit`.

## Out of scope

- Bundling `solc`/`slither` binaries into the wheel (explicit phase-3.md
  non-goal).
- Renaming the GitHub repo (stays `AURA`) or the importable Python package
  (stays `aura`) — only the PyPI distribution name changes.
- Creating GitHub Releases / release notes automation — phase-3.md's ask is
  PyPI publishing, not a release-notes pipeline.
- Actually pushing a release tag / performing the first real PyPI publish —
  that's a user action after the plan's manual-setup checklist, not something
  done as part of this implementation.

## Testing

- Existing test suite (`pytest -q`) must stay green, including
  `test_phase0_cli.py`'s version-format assertions.
- New/updated coverage: a test (or manual-verification note, if a real
  install is impractical in CI) confirming `aura --version` / `aura version`
  still work post-rename, and that `python -m build` succeeds locally
  producing a wheel whose metadata name is `aura-audit`.
- `release.yml`'s publish step cannot be tested end-to-end without a real
  PyPI project + trusted publisher registration; the plan will call out
  build-step verification (`python -m build`, inspecting the wheel) as the
  practical ceiling for automated verification here.
