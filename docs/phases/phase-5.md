# Phase 5 — Source-text analysis endpoint + deployed backend

**Status:** planned

## Why
The web UI's "paste" mode is broken by design: it sends a fake path
(`/tmp/aura_paste.sol`) and never uploads the source, and no backend is actually
deployed (`render.yaml` ships only the static frontend to a placeholder URL).

## What v1 of this does
- Add an endpoint that accepts **source text** (not just a server-side path),
  writes it to a sandboxed temp file, analyzes it, and cleans up.
- Wire the frontend paste mode to it.
- Deploy the FastAPI backend (Dockerized, with `solc`/`slither`) and point
  `VITE_API_BASE_URL` at it.
- Replace the in-memory `FAKE_DB` audit store with the real SQLModel persistence
  so History is durable.

## Out of scope
- Auth / multi-tenant accounts; rate limiting beyond basic protection.

## Success criteria
- Pasting a contract in the deployed UI returns real findings end-to-end
- History survives a backend restart
