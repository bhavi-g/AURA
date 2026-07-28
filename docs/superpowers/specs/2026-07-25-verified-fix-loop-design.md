# Design: Verified fix loop (Phase 1)

**Status:** approved
**Phase:** [docs/phases/phase-1.md](../../phases/phase-1.md)
**ADR:** [0004-verified-fix-loop](../../adr/0004-verified-fix-loop.md)
**Date:** 2026-07-25

## Problem

`aura fix <target> --rule <id>` currently generates an LLM diff and prints it —
nothing confirms the diff applies, compiles, or actually removes the
vulnerability. For a security tool whose differentiator is "PR-ready diffs,"
an unverified diff is a liability, not a feature.

## Goal

Before a fix is presented as usable, verify it in an isolated workspace:
apply → compile → re-analyze → confirm the target finding is gone and no new
findings were introduced. Retry with error feedback when verification fails.
Degrade honestly (never silently claim success) when `solc`/the analyzer
aren't available.

## Architecture

Extract fix-generation out of `cli.py` into a new core module, matching the
existing pattern where `core/` stays interface-agnostic (ADR 0001) and `cli.py`
is a thin dispatcher.

**New: `src/aura/core/fix.py`**

- `generate_fix_diff(finding, source_text, rule, *, llm, error_context=None) -> str`
  Builds the remediation prompt (moved from `cli.py`'s inline `fix_prompt`
  construction) and calls the LLM. When `error_context` is provided (a prior
  attempt's failure reason), it's appended to the prompt so the next attempt
  can correct course.

- `verify_fix(target_path, diff_text) -> VerifyResult`
  Runs one verification pass in an isolated temp workspace (see below).

- `verify_fix_loop(target_path, finding, rule, *, llm, max_retries=3) -> VerifyResult`
  Orchestrates: generate → verify → on non-`VERIFIED` result, retry with the
  failure as `error_context`, up to `max_retries` attempts total. Returns the
  last result once `VERIFIED` is reached or attempts are exhausted.

**`VerifyResult` (dataclass):**
```python
verdict: Literal["VERIFIED", "REGRESSED", "FAILED", "UNVERIFIED"]
diff: str
attempts: int
detail: str                    # human-readable reason
degraded_reason: str | None    # e.g. "solc not found" — set only for UNVERIFIED
new_findings: list[Finding]    # populated only for REGRESSED
```

**`cli.py`'s `fix_cmd`** becomes: resolve the matching finding (existing logic,
unchanged) → call `verify_fix_loop` → print verdict + diff + reasoning →
if `--write` and verdict is `VERIFIED`, apply the diff to the real file.

## Verification workspace

Each `verify_fix` call:
1. `tempfile.mkdtemp()` — a fresh directory, never inside the repo.
2. Copy the target file into it; `git init -q` the workspace so `git apply`
   has a valid tree to operate on.
3. `git apply` the diff.
   - Apply failure → `FAILED`, `detail` = git's stderr.
4. Compile the patched file with `solc`.
   - Compile failure → `FAILED`, `detail` = solc's stderr.
5. Re-run the analyzer (Slither) on the patched copy.
6. Compare findings against the original, matched by **`(rule_id, function)`**
   — chosen over exact line match (patches shift line numbers) and over
   rule-id-only (too coarse for files with multiple instances of the same
   rule in different functions). If a finding's `function` is `null`
   (contract-level issues have no function, per `slither_adapter.py`), fall
   back to matching on `rule_id` alone for that finding:
   - Target finding gone, no new findings → **`VERIFIED`**
   - Target finding gone, new findings appeared → **`REGRESSED`**
   - Target finding still present → **`FAILED`**

The workspace is discarded after each attempt (`tempfile` auto-cleanup); a
retry starts from a fresh copy of the pristine original file, so failed
attempts never compound.

## Degradation

Checked once per `verify_fix_loop` call, not per attempt:

| Condition | Verdict ceiling | Notes |
|---|---|---|
| `solc` missing | `UNVERIFIED (apply-only)` | Skip compile + re-analyze entirely |
| `solc` present, analyzer unavailable | `UNVERIFIED (compile-only)` | Skip re-analyze only |
| Both present | Full verification | As described above |
| LLM declines (`# ...` no-safe-fix marker) | `FAILED`, no retry | Nothing to apply — don't burn an attempt |

`UNVERIFIED` is a distinct verdict from `VERIFIED` in every surface (CLI text,
`--json`, `--write` gate) — it must never be presented as a success.

## CLI contract (new)

```
aura fix <target> --rule <id> [--write] [--max-retries N] [--json]
```

- Default `max-retries`: 3
- `--write` only touches the real file when the final verdict is `VERIFIED`;
  otherwise it refuses and prints why (verdict + last `detail`)
- `--json` mirrors the existing pattern on `analyze`: emits `VerifyResult`
  as JSON instead of the text summary
- No existing tested CLI output shape is touched — `fix` currently has no
  test coverage, so this is a new contract, not a breaking change

## Testing

Fixture: `contracts/Reentrancy.sol` (known-vulnerable, already in the repo).
The LLM must be **injectable/mockable** in tests — `generate_fix_diff` and
`verify_fix_loop` take `llm` as a parameter rather than constructing `LLM()`
internally, so tests control exactly which diff comes back per attempt without
depending on a real API call.

Cases:
1. A correct hand-written diff → `VERIFIED`
2. A diff that doesn't apply (malformed) → `FAILED` after 3 attempts, `detail`
   contains the git-apply error
3. A diff that compiles but doesn't touch the vulnerable code → `FAILED`
4. `shutil.which` mocked to hide `solc` → `UNVERIFIED (apply-only)`, no crash
5. `shutil.which` mocked to hide the analyzer only → `UNVERIFIED (compile-only)`
6. LLM returns a `# no safe fix` marker → `FAILED` immediately, `attempts == 1`

## Out of scope (unchanged from phase-1.md)

- Multi-file / cross-contract patches
- Auto-opening a PR with the verified fix (Phase 4)
- Switching LLM provider (Phase 2)
