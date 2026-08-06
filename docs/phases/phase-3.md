# Phase 3 — PyPI publish + install polish

**Status:** done (2026-08-05) — PRs [#33](https://github.com/bhavi-g/AURA/pull/33), [#34](https://github.com/bhavi-g/AURA/pull/34); released as [`aura-audit` v0.5.0](https://pypi.org/project/aura-audit/0.5.0/) on PyPI
**ADR:** [0005-dynamic-versioning-trusted-publishing](../adr/0005-dynamic-versioning-trusted-publishing.md)

## Why
The #1 adoption blocker for an OSS CLI is install friction. `pipx install aura-audit`
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
- `pipx install aura-audit` on a clean machine yields a working `aura` CLI
- Prereqs documented and reproducible from the README alone
