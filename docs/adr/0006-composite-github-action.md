# 0006 — Composite GitHub Action at the repo root

**Status:** accepted
**Date:** 2026-08-09

## Context

Phase 4 ships AURA as a GitHub Action. Two packaging choices had to be made:
container vs. composite, and same-repo vs. a dedicated actions repo.

A Docker container action would pin Python, `solc`, and Slither into one
reproducible image. It also means building, publishing, and patching that
image, and paying an image pull on every run.

## Decision

A **composite action**, defined in **`action.yml` at the repo root**, so
consumers write `uses: bhavi-g/AURA@<ref>`.

Reproducibility is recovered through inputs rather than an image:
`solc-version` pins the compiler and `aura-version` pins the AURA release.

The action's Python glue lives in `action/scripts/`, resolved at runtime via
`PYTHONPATH: ${{ github.action_path }}`, and is pruned from the sdist in
`MANIFEST.in` so it never ships inside the `aura-audit` wheel.

## Consequences

- No image to build, publish, or keep patched; startup is a `pip install`.
- Consumers who want byte-for-byte reproducibility must pin `aura-version`
  and `solc-version` themselves; the defaults track latest.
- The action version and the PyPI release version share a tag, so an action
  fix requires cutting a release tag even when no Python code changed.
- A second repo for the action was rejected: it would split the ADRs, tests,
  and release process across two places for no benefit at this size.
