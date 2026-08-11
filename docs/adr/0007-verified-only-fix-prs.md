# 0007 — Auto-opened fix PRs carry VERIFIED fixes only

**Status:** accepted
**Date:** 2026-08-09

## Context

Phase 4's action can open pull requests containing AURA-generated
remediations. An automated PR against someone's contracts is the highest-
trust action AURA takes: a wrong patch to a Solidity contract is not a
cosmetic bug.

ADR 0004 established the verified-fix loop — apply, compile, re-analyze —
producing verdicts VERIFIED / REGRESSED / FAILED / UNVERIFIED.
`docs/NEVER_DO.md` forbids claiming a fix is safe without verification.

## Decision

Only **VERIFIED** results may reach an auto-opened PR. Two independent
gates enforce this:

1. `aura fix --write` already refuses to write anything but VERIFIED
   (existing behavior in `cli.py::fix_cmd`).
2. `action/scripts/fixes.py::verified()` filters the result set again
   before any branch is committed or PR opened.

If nothing verifies, no PR is opened at all — an empty or speculative PR is
worse than silence. The PR body states the verification guarantee and
carries the not-an-audit disclaimer.

## Consequences

- Fix PRs are rarer but trustworthy: the review question becomes "do I want
  this change?" rather than "does this change even work?"
- REGRESSED/FAILED/UNVERIFIED outcomes are invisible to the PR author except
  as an absent fix PR. Surfacing them per-rule is possible future work.
- Fix PRs require an LLM API key; without one the provider abstraction falls
  back to a deterministic stub that cannot produce a patch, so the step
  skips and says so in the PR comment.
