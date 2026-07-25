# Phase 3 — PyPI publish + install polish

**Status:** planned

## Why
The #1 adoption blocker for an OSS CLI is install friction. `pipx install aura`
should just work.

## What v1 of this does
- Finalize packaging metadata (name, version, entry point, classifiers, README).
- Publish to PyPI (via a release GitHub Action / trusted publishing).
- Document `solc`/`slither` prerequisites and provide a one-command setup
  (e.g. `solc-select`, pipx for slither), matching what CI already does.
- Clear "getting started on a clean machine" section in the README.

## Out of scope
- Bundling solc/slither binaries into the wheel.

## Success criteria
- `pipx install aura` on a clean machine yields a working `aura` CLI
- Prereqs documented and reproducible from the README alone
