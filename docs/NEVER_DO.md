# NEVER DO — AURA guardrails

Guardrails written *before* the mistakes happen. If a change would violate one of
these, stop and reconsider.

## Security / trust
- **Never present AURA output as an audit.** It assists; it does not replace
  professional audits or formal verification. Keep the disclaimer in user-facing output.
- **Never claim a fix is safe without verification.** A generated diff is a
  *suggestion* until it has been applied, compiled, and re-analyzed (see P1).
- **Never commit secrets.** No `.env`, API keys, or tokens in git. `.env` is
  gitignored — keep it that way. Use `.env.example` with placeholders only.
- **Never log full contract source or LLM keys** in reports or CI output.

## Correctness / scope
- **Never silently change public behavior tests depend on.** The CLI/API output
  shapes are asserted by tests (e.g. `Findings: N | Score: S`, `/analyze` minimal
  response). Preserve them or update tests deliberately in the same change.
- **Never let an analyzer crash the pipeline.** Adapters degrade to `[]` on
  missing tools / parse errors. Keep that behavior.
- **Never expand scope mid-phase.** One phase file at a time. New ideas go to the
  backlog in `PROJECT_BRIEF.md`, not into the current change.

## Process
- **Never write code before reading** the latest `docs/sessions/` log and the ADR
  index (`docs/adr/README.md`).
- **Never make a real architectural decision without an ADR.** If you'd have to
  explain "why" to a future contributor, it's an ADR.
- **Never close a session without** a session log and a commit/push.
- **Never use a heavyweight model for routine work.** Default to Sonnet; reserve
  Opus/Fable for genuinely hard calls, and log that work separately (Phase 5 of
  the workflow checklist).
