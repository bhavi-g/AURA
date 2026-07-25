# Phase 4 — GitHub Action (SARIF Code Scanning + PR comments)

**Status:** planned

## Why
Meet developers where they review code. AURA already emits SARIF; surfacing it
in GitHub Code Scanning and as PR comments is the top adoption surface.

## What v1 of this does
- A composite/Docker GitHub Action that runs `aura analyze` on changed contracts.
- Upload SARIF to GitHub Code Scanning (`upload-sarif`).
- Post a concise PR comment summarizing findings (and, once P1 lands, verified fixes).
- A copy-paste workflow snippet in the README.

## Out of scope
- A hosted GitHub App; auto-opening fix PRs (possible later, builds on P1).

## Success criteria
- Adding the Action to a repo shows AURA findings in the PR's "Files changed" / Security tab
- Runs green on this repo's own contracts as a dogfood test
