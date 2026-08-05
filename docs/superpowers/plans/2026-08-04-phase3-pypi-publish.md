# Phase 3 — PyPI Publish + Install Polish — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `aura` installable via `pipx install aura-audit` / `pip install aura-audit`, with automated PyPI publishing on tag push and accurate docs.

**Architecture:** Rename the PyPI distribution (not the importable package or CLI command) to `aura-audit`, switch to git-tag-derived versioning via `setuptools_scm`, complete packaging metadata + LICENSE, add a trusted-publishing release workflow, and bring the README/CI in line.

**Tech Stack:** Python 3.11+, setuptools + setuptools_scm build backend, GitHub Actions (`pypa/gh-action-pypi-publish`), Poetry for local dev.

## Global Constraints

- PyPI distribution name: `aura-audit`. Importable package stays `aura` (`src/aura/...`); CLI command stays `aura`. (Spec §1)
- Version is derived from git tags via `setuptools_scm`; no hand-edited version string. `fallback_version = "0.0.0"` for tagless/shallow builds. (Spec §2)
- `requires-python = ">=3.11"` everywhere it's stated (code already requires 3.11+; only the README was stale). (Spec §5)
- License: MIT — add the missing `LICENSE` file; this completes an already-declared decision (README already says MIT), not a new one. (Spec §3)
- Out of scope: bundling `solc`/`slither` in the wheel; renaming the GitHub repo or the `aura` Python package; GitHub Releases/release-notes automation; actually pushing a release tag or performing the first real PyPI publish. (Spec "Out of scope")
- Preserve tested CLI output shapes (`docs/NEVER_DO.md`) — `aura --version` / `aura version` must still print `AURA v<version>` / `<version>`.
- This repo's convention (see `git log`) is feature branch → PR → squash-merge into `main`, not direct pushes to `main`.

---

### Task 1: Working branch + LICENSE + pyproject.toml packaging metadata

**Files:**
- Create: `LICENSE`
- Modify: `pyproject.toml` (whole `[build-system]` and `[project]` sections)

**Interfaces:**
- Produces: PyPI distribution name `aura-audit`, dynamic version via `setuptools_scm`, `[tool.setuptools_scm].fallback_version = "0.0.0"` — later tasks (2, 3, 5) depend on this name and on `python -m build` working.

- [ ] **Step 1: Create the working branch**

```bash
git checkout -b phase-3-pypi-publish
```

- [ ] **Step 2: Add the LICENSE file**

Create `LICENSE` with this exact content (standard MIT license text, copyright holder matching the README's existing MIT claim):

```
MIT License

Copyright (c) 2026 Bhavish Goyal

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 3: Update `pyproject.toml`'s `[build-system]` and `[project]` sections**

Replace the current top of the file (from `[build-system]` through the end of `[project.optional-dependencies]`, i.e. everything before `[tool.setuptools.package-dir]`) with:

```toml
[build-system]
requires = ["setuptools>=64", "setuptools_scm>=8", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "aura-audit"
description = "Solidity smart-contract security tool: detect vulnerabilities, explain them in plain English, and generate verified fix diffs."
readme = "README.md"
license = { text = "MIT" }
authors = [
  { name = "Bhavish Goyal" },
]
requires-python = ">=3.11"
dynamic = ["version"]
classifiers = [
  "Development Status :: 4 - Beta",
  "Environment :: Console",
  "Intended Audience :: Developers",
  "License :: OSI Approved :: MIT License",
  "Programming Language :: Python :: 3.11",
  "Topic :: Security",
]
dependencies = [
  "fastapi",
  "uvicorn",
  "typer",
  "sqlmodel>=0.0.22",
  "sqlalchemy>=2.0",
  "pydantic>=2.0",
    "openai>=1.55.0,<2.0.0",
  "anthropic>=0.47.0,<1.0.0",
]

[project.urls]
Homepage = "https://github.com/bhavi-g/AURA"
Repository = "https://github.com/bhavi-g/AURA"
Issues = "https://github.com/bhavi-g/AURA/issues"

[project.scripts]
aura = "aura.cli:app"

[project.optional-dependencies]
dev = [
  "pytest>=7.4",
  "httpx>=0.27",       # Starlette TestClient dependency
  "requests>=2.31",
  "pre-commit>=3.7",
  "ruff>=0.4",
  "black>=24",
  "isort>=5.12",
  "build>=1.2",
]

[tool.setuptools_scm]
fallback_version = "0.0.0"
```

Note: the `openai` line's 4-space indent (vs. 2-space elsewhere) is preserved exactly as-is — `docs/PROJECT_BRIEF.md`'s backlog explicitly marks it "cosmetic... no action needed," so it's intentionally not touched here.

- [ ] **Step 4: Verify the file parses and `[tool.setuptools...]` sections below are untouched**

```bash
python -c "import tomllib; tomllib.load(open('pyproject.toml', 'rb')); print('OK')"
tail -10 pyproject.toml
```

Expected: prints `OK`, and the tail still shows the original `[tool.setuptools.package-dir]` / `[tool.setuptools.packages.find]` / `[tool.black]` / `[tool.isort]` / `[tool.ruff]` sections unchanged.

- [ ] **Step 5: Commit**

```bash
git add LICENSE pyproject.toml
git commit -m "feat: rename PyPI distribution to aura-audit, add dynamic versioning + packaging metadata"
```

---

### Task 2: Version resolution — `src/aura/__init__.py` and `src/aura/cli.py`

**Files:**
- Modify: `src/aura/__init__.py`
- Modify: `src/aura/cli.py:39-57`
- Test: `tests/test_phase0_cli.py` (existing, no edits — must still pass)

**Interfaces:**
- Consumes: distribution name `aura-audit` from Task 1.
- Produces: `aura.__version__` (str, PEP 440 format) importable from `aura`; `aura --version` / `aura version` CLI output — later tasks don't depend on this directly but it must not regress.

- [ ] **Step 1: Read the current `src/aura/__init__.py`**

Current content:
```python
__all__ = ["__version__"]
__version__ = "0.0.1"
```

- [ ] **Step 2: Replace it with metadata-based version resolution**

```python
from importlib import metadata

try:
    __version__ = metadata.version("aura-audit")
except metadata.PackageNotFoundError:
    __version__ = "0.0.0.dev0"

__all__ = ["__version__"]
```

- [ ] **Step 3: Update `src/aura/cli.py`'s two `metadata.version("aura")` calls to `"aura-audit"`**

In `version_cmd` (around line 43):
```python
@app.command("version")
def version_cmd() -> None:
    """Print CLI version in the format tests expect."""
    try:
        v = metadata.version("aura-audit")
    except metadata.PackageNotFoundError:
        v = "0.0.0-dev"
    typer.echo(f"AURA v{v}")
```

In `_version_callback` (around line 49-57):
```python
def _version_callback(value: bool | None) -> None:
    if value:
        try:
            v = metadata.version("aura-audit")
        except metadata.PackageNotFoundError:
            v = "0.0.0-dev"
        # tests that call `-m aura.cli --version` expect just the raw version
        typer.echo(v)
        raise typer.Exit()
```

- [ ] **Step 4: Reinstall editable so the new distribution metadata is registered**

```bash
poetry install
```

(This re-resolves `pyproject.toml`, including the `aura-audit` name and `setuptools_scm`-derived version, and re-registers the `aura` console script.)

- [ ] **Step 5: Run the version-specific tests**

```bash
PYTHONPATH="$(pwd)" poetry run pytest -q tests/test_phase0_cli.py -v
```

Expected: all 4 tests in that file pass, including `test_package_import_and_version` (regex match on `aura.__version__`) and `test_console_script_exists_and_works` (`aura version` prints `AURA v...`).

- [ ] **Step 6: Manually inspect the derived version**

```bash
PYTHONPATH="$(pwd)" poetry run python -c "import aura; print(aura.__version__)"
poetry run aura --version
```

Expected: both print a real `setuptools_scm`-derived version like `0.4.1.dev6+g<hash>` (based on the existing `v0.4.0` tag and commits since), not `0.0.1` or `0.0.0-dev`.

- [ ] **Step 7: Run the full test suite**

```bash
PYTHONPATH="$(pwd)" poetry run pytest -q
```

Expected: same pass count as before this change (89/89 per the last session log), no regressions.

- [ ] **Step 8: Commit**

```bash
git add src/aura/__init__.py src/aura/cli.py
git commit -m "fix: read version from aura-audit distribution metadata, not a hardcoded string"
```

---

### Task 3: CI checkout depth fix

**Files:**
- Modify: `.github/workflows/ci.yml:17-18` (test job) and `.github/workflows/ci.yml:71-72` (bench job)

**Interfaces:**
- Consumes: `setuptools_scm` from Task 1 (needs full git history + tags to resolve a version; a shallow clone breaks the editable install both CI jobs perform).

- [ ] **Step 1: Add `fetch-depth: 0` to the `test` job's checkout step**

Change:
```yaml
      - uses: actions/checkout@v4
```
(the first occurrence, under `jobs.test.steps`) to:
```yaml
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
```

- [ ] **Step 2: Add the same to the `bench` job's checkout step**

Change the second occurrence (under `jobs.bench.steps`) identically:
```yaml
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
```

- [ ] **Step 3: Verify YAML is well-formed**

```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml')); print('OK')"
```

Expected: prints `OK`. (Actual CI behavior can only be confirmed once this branch's PR runs — note this as the verification ceiling, same as the spec calls out for `release.yml`.)

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: fetch full git history so setuptools_scm can see tags"
```

---

### Task 4: Release workflow (`release.yml`)

**Files:**
- Create: `.github/workflows/release.yml`

**Interfaces:**
- Consumes: `python -m build` working against `pyproject.toml` from Task 1 (produces `aura_audit-*.whl` / `.tar.gz` in `dist/`).
- Produces: nothing later tasks depend on — this is the terminal deliverable for the "publish" half of phase 3. Requires manual one-time PyPI setup (documented in this task) before it can succeed on a real tag push; not executed as part of this plan.

- [ ] **Step 1: Create `.github/workflows/release.yml`**

```yaml
name: release

on:
  push:
    tags:
      - "v*"

concurrency:
  group: release-${{ github.ref }}
  cancel-in-progress: false

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Set up Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install build tool
        run: python -m pip install -U pip build

      - name: Build sdist and wheel
        run: python -m build

      - name: Upload build artifacts
        uses: actions/upload-artifact@v4
        with:
          name: dist
          path: dist/

  publish:
    needs: [build]
    runs-on: ubuntu-latest
    environment: pypi
    permissions:
      id-token: write
    steps:
      - name: Download build artifacts
        uses: actions/download-artifact@v4
        with:
          name: dist
          path: dist/

      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1
```

- [ ] **Step 2: Verify YAML is well-formed**

```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/release.yml')); print('OK')"
```

Expected: prints `OK`.

- [ ] **Step 3: Verify the build step this workflow runs actually works, locally**

```bash
rm -rf dist/
poetry run python -m pip install build
poetry run python -m build
ls dist/
```

Expected: `dist/` contains `aura_audit-<version>-py3-none-any.whl` and `aura_audit-<version>.tar.gz`. Inspect the wheel's declared name/version:

```bash
unzip -p dist/aura_audit-*.whl '*.dist-info/METADATA' | grep -E "^(Name|Version):"
```

Expected: `Name: aura-audit` and a `Version:` line matching the `setuptools_scm`-derived version from Task 2's Step 6.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/release.yml
git commit -m "ci: add PyPI trusted-publishing release workflow, triggered on v* tags"
```

**Manual setup required before this workflow can actually publish (not part of this plan's execution — do this when ready to cut the first real release):**
1. Create a PyPI account at https://pypi.org/account/register/ if you don't have one.
2. Go to https://pypi.org/manage/account/publishing/ and register a new "pending trusted publisher" for a project named `aura-audit` (the project doesn't need to exist yet — PyPI allows registering the trusted publisher first):
   - PyPI project name: `aura-audit`
   - Owner: `bhavi-g`
   - Repository name: `AURA`
   - Workflow filename: `release.yml`
   - Environment name: `pypi`
3. In the GitHub repo (`bhavi-g/AURA`) → Settings → Environments, create an environment named `pypi` (matches `environment: pypi` in the workflow above). Optionally add protection rules (e.g. required reviewers) so tag pushes don't auto-publish without a check.
4. To cut the first release: bump nothing by hand (version comes from the tag) — just `git tag v0.5.0 && git push origin v0.5.0`. Watch the Actions tab for the `release` workflow.

---

### Task 5: README updates

**Files:**
- Modify: `README.md` (the "Installation" section, roughly lines 20-33 per the version read during design)

**Interfaces:**
- Consumes: `aura-audit` as the pip-installable name (Task 1); no code interfaces.

- [ ] **Step 1: Replace the "Installation" section**

Find:
```markdown
## Installation

AURA currently runs as a **CLI tool**.

### Prerequisites

* Python 3.10+
* Poetry
* `solc` available in PATH
* Slither installed

### Install dependencies

```bash
poetry install
```

---
```

Replace with:
```markdown
## Installation

AURA currently runs as a **CLI tool**.

### Prerequisites

* Python 3.11+
* `solc` and Slither available on `PATH` (see below)

### Install AURA

Recommended — isolated CLI install via [pipx](https://pipx.pypa.io/) (requires
`pipx`: `python -m pip install --user pipx && pipx ensurepath`):

```bash
pipx install aura-audit
```

Or with pip:

```bash
pip install aura-audit
```

Either way, the installed command is `aura` — `aura-audit` is just the PyPI
distribution name (`aura` was already taken by an unrelated project).

### Install solc and Slither

AURA's analyzers shell out to `solc` and Slither, which are not bundled with
the pip package and need to be on `PATH` separately:

```bash
pipx install solc-select
solc-select install 0.8.20
solc-select use 0.8.20

pipx install slither-analyzer
```

### Contributing / running from source

```bash
poetry install
poetry run aura --help
```

---
```

- [ ] **Step 2: Review the rendered diff**

```bash
git diff README.md
```

Confirm no other section was accidentally touched (the rest of the README — Basic Usage, Limitations, Project Status, License — should show zero diff).

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: document pipx install path and fix stale Python version prereq"
```

---

### Task 6: Full verification, session log, PR

**Files:**
- Create: `docs/sessions/2026-08-04-session.md`
- No other file changes (verification + process only)

- [ ] **Step 1: Run the full test suite one more time on the final branch state**

```bash
PYTHONPATH="$(pwd)" poetry run pytest -q
```

Expected: all tests pass, same count as Task 2 Step 7.

- [ ] **Step 2: Run lint/format checks (matches CI)**

```bash
poetry run ruff check .
poetry run black --check .
poetry run isort --check-only .
```

Expected: all clean (no output / exit 0).

- [ ] **Step 3: Write the session log**

Use `docs/sessions/TEMPLATE.md`'s structure. Create `docs/sessions/2026-08-04-session.md` covering: what was built (distribution rename to `aura-audit`, `setuptools_scm` versioning, packaging metadata + LICENSE, CI fetch-depth fix, `release.yml`, README updates), what works (test/lint results from Steps 1-2), what's left (the manual PyPI trusted-publisher setup from Task 4, and actually cutting the first tag — both explicitly deferred to the user), and confirm no new ADR is needed (packaging mechanics, not an architectural decision the codebase's future contributors would need explained).

- [ ] **Step 4: Push the branch and open a PR**

```bash
git push -u origin phase-3-pypi-publish
gh pr create --title "Phase 3: PyPI publish + install polish" --body "$(cat <<'EOF'
## Summary
- Rename the PyPI distribution to `aura-audit` (`aura` is taken); the `aura` CLI command and Python package are unchanged.
- Derive the version from git tags via setuptools_scm instead of a hardcoded `0.0.0`.
- Complete packaging metadata (description, classifiers, license, urls) and add the missing LICENSE file.
- Fix CI's shallow checkout so setuptools_scm can see tags.
- Add a trusted-publishing release workflow (`release.yml`, triggered on `v*` tags) — requires one-time manual PyPI setup before the first real publish (documented in the workflow's task in the implementation plan).
- Update the README's install instructions and fix the stale Python 3.10+ prereq.

## Test plan
- [x] `pytest -q` full suite green
- [x] `ruff check .` / `black --check .` / `isort --check-only .` clean
- [x] `python -m build` produces a wheel with `Name: aura-audit` and a real derived version
- [ ] CI green on this PR (confirms the `fetch-depth: 0` fix works in practice)
- [ ] First real PyPI publish — deferred until the manual trusted-publisher setup is done (see PR description / plan Task 4)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 5: Commit the session log**

```bash
git add docs/sessions/2026-08-04-session.md
git commit -m "docs: add 2026-08-04 session log"
git push
```

Expected: PR shows the session-log commit added; wait for CI to go green before merging (per repo convention — squash-merge once green).
