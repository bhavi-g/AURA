# 0002 — Slither as primary detector; Mythril optional

**Status:** accepted (backfilled 2026-07-24)

## Context
Rule-based static analysis of Solidity is a solved-enough problem with mature
tools. Slither is fast, widely used, and emits structured JSON. Mythril adds
symbolic execution but is slow and heavier to install.

## Decision
Slither is the primary detector (`slither_adapter`), invoked via CLI with a pipx
fallback and defensive JSON extraction. Mythril (`mythril_adapter`) runs
opportunistically and **degrades to `[]`** if `myth` is not on PATH. Both
normalize to a common `Finding` dict consumed by scoring/reporting.

## Consequences
- The pipeline never hard-fails on a missing/misbehaving analyzer.
- Adding analyzers = add an adapter that returns normalized `Finding`s.
- `solc` must be present; CI installs it via `solc-select`.
