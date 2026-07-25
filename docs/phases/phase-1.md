# Phase 1 — Verified fixes (closed loop)

**Status:** planned (next up)
**ADR:** [0004-verified-fix-loop](../adr/0004-verified-fix-loop.md)

## Why
Today `aura fix` stops at "the LLM emitted a diff." For an OSS security tool,
un-verified fixes are a liability — nobody should open a PR from a diff we
haven't checked. This phase makes "PR-ready" mean something.

## What v1 of this does
Extend the fix flow so a generated diff is **verified before it is presented**:

1. Generate the unified diff (existing behavior).
2. Copy the target into a temp workdir; `git apply` the diff there.
3. Compile check with `solc` — does it still compile?
4. Re-run the analyzer on the patched copy.
5. Compare findings and emit a verdict:
   - `VERIFIED` — target finding gone, still compiles, no new findings
   - `REGRESSED` — compiles and finding gone, but new findings appeared
   - `FAILED` — didn't apply, didn't compile, or the finding remains
6. On failure, feed the compiler/analyzer error back to the LLM and retry (bounded, e.g. ≤3).
7. `--write` applies the verified patch to the user's file; default is dry-run.

## Degradation
If `solc`/analyzer isn't available, fall back to **compile-only** (or apply-only)
verification and label the verdict as `UNVERIFIED (compile-only)` rather than
claiming success.

## Out of scope (this phase)
- Multi-file / cross-contract patches
- Opening the PR automatically (that's P4)
- Switching LLM provider (that's P2)

## Success criteria
- `aura fix <target> --rule <id>` reports a verdict, not just a diff
- A known-vulnerable sample (e.g. `contracts/Reentrancy.sol`) reaches `VERIFIED`
- The user's file is never modified without `--write`
- Tests cover: apply-fail, compile-fail, finding-remains, verified-success paths
