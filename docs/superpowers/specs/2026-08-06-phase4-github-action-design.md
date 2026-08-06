# Phase 4 — GitHub Action (SARIF Code Scanning + PR comments) — Design

**Status:** approved
**Phase:** `docs/phases/phase-4.md`
**Date:** 2026-08-06

## Why

AURA is installable (P3) but only runs when a developer remembers to run it.
The adoption surface that matters is code review: findings on the PR, in the
Security tab, without anyone typing a command. Phase 4 ships a GitHub Action
that does that.

This phase is scoped to be **complete** — nothing inside it is deferred to a
later pass. That includes the severity gate and auto-opened fix PRs, both of
which could plausibly have been punted; they are in scope here.

## The gap this starts from

`aura analyze` today writes JSON and Markdown reports (`pipeline.py`
`run_analysis()` → `write_json` / `write_md`). It does **not** write SARIF.
SARIF is only produced by `tools/post_analyze.py`, a repo-internal script that
re-reads `reports/slither_parsed.json` off disk and calls `write_sarif()`.
That script is not part of the published `aura-audit` distribution
(`MANIFEST.in` prunes the sdist to package essentials; `tools/` is not in the
wheel).

So an Action that runs in *someone else's* repo has no way to get SARIF out of
AURA today. Closing that is decision 1.

## Decisions

### 1. `aura analyze --sarif <path>`

Add an optional `--sarif` output flag to the existing `analyze` command in
`src/aura/cli.py`, alongside the existing `--json` flag:

```python
sarif_out: str = typer.Option("", "--sarif", help="Also write a SARIF report to this path"),
```

When non-empty, `analyze` calls `write_sarif(res["findings"], sarif_out)` —
the existing helper in `src/aura/core/reporting/sarif_report.py`, unchanged —
on the in-memory findings returned by `run_analysis()`. No disk round-trip
through `reports/slither_parsed.json`, and no dependency on
`tools/post_analyze.py`.

**Output-shape safety** (`docs/NEVER_DO.md`: never silently change public
behavior tests depend on): the flag is additive and defaults off. With
`--sarif` absent, `analyze`'s stdout is byte-identical to today's
(`Findings: N | Score: S`, or the `--json` payload). With `--sarif` present,
stdout is *still* unchanged — the SARIF goes to the file only. Confirmation
that the file was written is not printed, to keep `--json`'s stdout pure
machine-readable JSON.

`tools/post_analyze.py` stays as-is. It serves the existing
`upload-sarif.yml` push-to-main workflow and this phase has no reason to
touch it.

### 2. Composite action at repo root (`action.yml`)

A composite action, not a Docker container action. Rationale: no image to
build, publish, or keep patched; startup is a `pip install` rather than an
image pull; and the runner already has Python and the `gh` CLI. The cost is
less hermetic pinning, which the `aura-version` and `solc-version` inputs
mitigate.

It lives at the repo root as `action.yml`, so consumers reference it as
`uses: bhavi-g/AURA@v0.6.0`. This is the conventional layout and requires no
second repository.

**Inputs:**

| Input | Default | Purpose |
|---|---|---|
| `path` | `.` | Target passed to `aura analyze` |
| `solc-version` | `0.8.20` | Installed and selected via `solc-select` |
| `aura-version` | `""` (latest) | Pin the `aura-audit` release; empty = latest on PyPI |
| `github-token` | `${{ github.token }}` | Used for PR comment + fix-PR API calls |
| `fail-on` | `high` | Severity gate threshold: `critical`/`high`/`medium`/`low`/`none` |
| `llm-provider` | `""` | Sets `AURA_LLM_PROVIDER` (`anthropic`/`openai`) |
| `llm-api-key` | `""` | Maps to `ANTHROPIC_API_KEY`/`OPENAI_API_KEY` by provider |
| `open-fix-prs` | `true` | Whether to open the aggregated verified-fix PR |

**Outputs:** `findings-count`, `score`, `sarif-path`.

**Step order** (fixed, and depended on by later sections):

1. `setup-python@v5` (3.11)
2. `pip install aura-audit[==version]` + `slither-analyzer`
3. `solc-select install/use`
4. `aura analyze` with `--json` and `--sarif`
5. `github/codeql-action/upload-sarif@v3`
6. Fix PRs (if enabled) — before the comment, so the comment can link the PR
7. PR comment — reports findings, gate outcome, and fix-PR link together
8. Severity gate — **last**, so a failure never suppresses the surfaces above

Steps 5–7 are guarded `if: always()` so an earlier non-zero exit still
surfaces results.

Checkout is the **caller's** responsibility (composite actions do not check
out for you), and the caller must use `fetch-depth: 0` so the changed-file
diff against the PR base works. The README snippet and the action's own
docs state this.

Because a composite action inherits the caller's permissions, the calling
workflow must grant: `contents: write` (fix-PR branch pushes; `read` suffices
if `open-fix-prs: false`), `security-events: write` (SARIF upload),
`pull-requests: write` (comment + PR). These are ceilings, not guarantees —
on fork PRs GitHub caps `GITHUB_TOKEN` at read-only regardless (see the
fix-PR guards in decision 6).

### 3. Scan scope: full path, filter the comment

`aura analyze` runs against `path` (default the whole repo), not against the
changed files individually. Slither needs whole-project context to resolve
imports; feeding it an arbitrary subset of a PR's `.sol` files produces false
negatives when a changed contract imports an unchanged one.

The **SARIF upload is therefore the full result set**, which is the correct
and conventional Code Scanning behavior — GitHub itself handles surfacing only
PR-relevant alerts in the "Files changed" view.

The **PR comment** is filtered to findings whose location file is in the PR's
changed-file set, computed as:

```
git diff --name-only origin/<base-ref>...HEAD
```

with the base ref from `github.event.pull_request.base.ref`. Finding paths
and git paths are both normalized to repo-relative POSIX form before
comparison. If the diff command fails (shallow checkout, missing base), the
comment degrades to showing all findings with an explicit note rather than
silently showing none.

### 4. PR comment: upsert, not append

The comment body carries a hidden marker:

```html
<!-- aura-pr-comment -->
```

Before posting, the action lists the PR's comments (`gh api`), finds the
first authored by the token's identity containing that marker, and **edits it
in place**. Only when none exists does it create one. A PR with six pushes
gets one comment with the latest results, not six comments.

Body content: a header line with total findings and score, a severity
breakdown table, the top findings in changed files (rule, severity,
`file:line`, title), a line stating whether the severity gate passed, a line
about the fix PR (link, or why it was skipped), and the standing "AURA
assists; it is not an audit" disclaimer required by `docs/NEVER_DO.md`.

### 5. Severity gate (`fail-on`)

After analysis, findings are compared against the threshold using the ordering
`CRITICAL > HIGH > MEDIUM > LOW > INFO`. If any finding's severity is at or
above the threshold, the step exits non-zero and the check fails.
`fail-on: none` disables the gate entirely.

The gate is implemented in the action's glue script, **not** as a new CLI
flag or exit-code change in `aura analyze` — `analyze` exiting non-zero on
findings would change behavior that existing tests assert.

The gate is the **last** step (step 8 above). Everything a developer needs —
SARIF alerts, the PR comment, the fix PR — is already published by the time
the check turns red, so a failing gate is informative rather than a dead end.

### 6. Auto-opened verified-fix PRs

This is possible without any hosted infrastructure: `aura fix` (ADR 0004,
already shipped) plus `git` and `gh`, all inside the consumer's own runner.

For each changed `.sol` file, for each distinct `rule_id` among that file's
findings, the action runs:

```
aura fix <file> --rule <rule_id> --write --json
```

`--write` only writes when the verdict is `VERIFIED` (existing behavior in
`cli.py::fix_cmd`), so unverified diffs can never reach the branch. This
directly honors `docs/NEVER_DO.md`'s "never claim a fix is safe without
verification" — the PR contains only apply→compile→re-analyze-verified
changes, and its body labels each one with the rule it resolves.

`aura fix` exits 1 on `FAILED`/`REGRESSED`; the loop tolerates that per-rule
and continues, since one unfixable rule should not abort the others.

All resulting file changes are committed to a **stable branch**
`aura/auto-fixes/pr-<N>`, force-pushed, and opened as a **single aggregated
PR** against the source PR's head branch. Re-runs update that same branch and
PR (upsert, mirroring the comment). One PR per source PR, not one per fix.

**Guards:**
- Skipped entirely when no `llm-api-key` is supplied — without a provider,
  `LLM()` falls back to the deterministic stub, which cannot produce a real
  patch. The PR comment states the skip reason instead of pretending.
- Skipped when `open-fix-prs: false`.
- Skipped when the triggering PR's head branch is itself an
  `aura/auto-fixes/*` branch, so the action cannot recurse on its own output.
- Skipped when nothing verified — no empty PR.
- Skipped for **fork PRs**. On `pull_request` from a fork, `GITHUB_TOKEN` is
  read-only regardless of the workflow's `permissions` block, so the branch
  push cannot succeed. Detected via
  `github.event.pull_request.head.repo.fork`, and reported in the comment as
  a skip reason rather than failing the run. (`pull_request_target`, which
  would grant write access, is deliberately not used: it runs workflow code
  with a privileged token against untrusted PR contents, and this action
  executes that PR's Solidity through Slither and an LLM.)

The single-file constraint of `aura fix` (`v1 does NOT` support multi-file
fixes) is inherited as-is; this phase does not attempt to lift it.

### 7. Glue code lives in `action/scripts/`, and is unit-tested

The changed-file filtering, comment rendering, severity gate, and fix-PR
orchestration are **stdlib-only Python scripts** under `action/scripts/`, not
inline `run: |` YAML blocks. Two reasons: logic embedded in YAML strings
cannot be unit-tested, and this is CI glue rather than library code, so it
does not belong in the installed `aura-audit` package either.

GitHub API calls go through the `gh` CLI (preinstalled on GitHub-hosted
runners), so the scripts need no HTTP dependency.

Pure functions (severity comparison, path normalization, changed-file
filtering, Markdown rendering) are unit-tested in `tests/test_action_scripts.py`
with no network and no subprocess. Subprocess-invoking functions take an
injectable runner so tests can assert on the constructed commands.

### 8. Dogfooding: `.github/workflows/aura-pr-scan.yml`

A new `pull_request`-triggered workflow using `uses: ./` (the in-repo action,
so a PR tests the action as modified by that same PR) against
`samples/contracts`, with the required `permissions` block. It sets
`fail-on: none` for this repo specifically — `samples/contracts` contains
intentionally vulnerable fixtures, so a gate would fail every PR by design —
and `open-fix-prs: false`, since auto-fixing deliberate vulnerability
fixtures would be nonsense.

The existing `upload-sarif.yml` (push-to-main baseline scan) is left
untouched; it serves a different trigger and this phase has no reason to
disturb it.

### 9. README

A "GitHub Action" section with a copy-paste workflow snippet, the full input
table, the required `permissions` block, the `fetch-depth: 0` requirement,
and a note that fix PRs need an LLM key.

## Out of scope

- **A hosted GitHub App.** Explicitly out of scope in `docs/phases/phase-4.md`,
  and structurally blocked: an App needs a persistent webhook-receiving
  deployed service, which does not exist (`PROJECT_BRIEF.md` "Known reality
  gaps": no backend is deployed; that is Phase 5). The Action delivers the
  same developer-facing outcome with no infrastructure.
- **Lifting `aura fix`'s single-file limitation** — a `v1 does NOT` item, and
  not something an Action wrapper can fix.
- **Marketplace publication** — a manual, human-performed listing step, not
  code.
- **Auto-detecting `solc` from pragma** — `solc-version` is an explicit input.

## Testing

- **`--sarif` flag:** unit tests in `tests/test_cli.py` — file is written, it
  parses as SARIF 2.1.0 with the expected `runs[0].results` shape, and
  stdout for both text and `--json` modes is unchanged versus a run without
  the flag.
- **Glue scripts:** `tests/test_action_scripts.py` covering severity ordering
  (including the gate's boundary: threshold severity itself fails), changed-file
  filtering (path normalization, empty diff, diff failure fallback), comment
  rendering (marker present, filtered content, skip reasons), and the fix
  loop's guards (no key → skip, recursion guard, fork PR → skip, nothing
  verified → no PR).
- **Action YAML:** validated by the dogfood workflow actually running on this
  phase's own PR — phase-4.md's success criterion ("runs green on this repo's
  own contracts") is verified by observing that check, not asserted from the
  source.
- **Whole suite:** `pytest -q` stays green (89 passing before this phase),
  plus `ruff` / `black` / `isort`, run from the venv rather than Poetry (see
  `PROJECT_BRIEF.md`'s tooling-drift note).

## Decisions worth an ADR

Two are genuine architectural decisions a future contributor would need
explained, and will be written as ADRs during implementation:

- **Composite action over Docker container action**, and root `action.yml`
  over a separate actions repo.
- **Auto-fix PRs restricted to `VERIFIED` verdicts only** — the credibility
  rule that makes automated PRs acceptable at all.
