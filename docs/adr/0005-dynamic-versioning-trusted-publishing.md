# 0005 — Dynamic versioning + PyPI trusted publishing

**Status:** accepted (2026-08-05) — implemented in [#33](https://github.com/bhavi-g/AURA/pull/33), [#34](https://github.com/bhavi-g/AURA/pull/34)

## Context
Phase 3 needed a versioning and release strategy for publishing `aura-audit`
to PyPI. Two decisions have knock-on effects across the build config, CI, and
the release workflow, and a future contributor would reasonably ask "why is
there no version number in `pyproject.toml`" and "why is there no PyPI token
secret in this repo" — so both are recorded here rather than left implicit.

## Decision
1. **Version is derived from git tags, not hand-edited.** `pyproject.toml`
   sets `dynamic = ["version"]` and `setuptools_scm` reads the version from
   the nearest git tag at build time (tag `v0.5.0` → package version
   `0.5.0`; commits after a tag get a PEP 440 dev suffix, e.g.
   `0.5.1.dev3+g1a2b3c4`). Tagging *is* the release action — there's no
   separate "bump the version in a file" step to forget or get out of sync
   with the tag.
2. **Publishing uses PyPI trusted publishing (OIDC), not a stored API
   token.** `.github/workflows/release.yml`'s `publish` job authenticates to
   PyPI via GitHub Actions' OIDC identity (`id-token: write`, scoped only to
   that job), matched against a "trusted publisher" registered on PyPI's
   project settings. No `PYPI_API_TOKEN` or other long-lived credential
   exists in this repo's secrets.

## Consequences
- Cutting a release is `git tag vX.Y.Z && git push origin vX.Y.Z` — nothing
  else needed in the repo itself.
- All three GitHub Actions workflow files (`ci.yml`'s two jobs,
  `upload-sarif.yml`, `release.yml`) need `fetch-depth: 0` on checkout so
  `setuptools_scm` can see tags. A shallow clone doesn't fail loudly — it
  silently derives a fabricated version from the bare commit hash instead
  (see `docs/PROJECT_BRIEF.md`'s "Tooling drift" backlog entry for the exact
  failure mode that motivated this).
- The PyPI distribution name (`aura-audit`) had to diverge from the
  importable package/CLI command (`aura`) because `aura` was already
  registered on PyPI by an unrelated project — unrelated to this ADR's two
  decisions, but worth knowing the two names aren't the same thing and why.
- Trusted publishing requires a one-time manual setup per PyPI project
  (registering the trusted publisher, matching repo/workflow/environment
  name — see `CONTRIBUTING.md`'s "Releasing" section) that can't be
  automated; it's a PyPI account action, not something CI can do for itself.
- PyPI versions are immutable once published (yank-only, not deletable). A
  tag pushed by mistake can't be un-published, only superseded by a new
  version — so `release.yml`'s `pypi` GitHub Environment exists as a place
  to attach manual-approval protection rules if that's ever wanted.
