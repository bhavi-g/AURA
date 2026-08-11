AURA

**AURA (Automated Understanding & Remediation for Audits)** is a smart contract security tool that helps developers move from **vulnerability detection → explanation → fix**.

Most tools stop at reporting issues.
AURA goes one step further by generating **review-ready code diffs** developers can use during development and code review.

Website: https://aura-yab0.onrender.com

---

## What AURA does (in one minute)

**You give AURA**

* A Solidity smart contract (file or folder)

**AURA gives you**

* Detected security issues (rule-based)
* Plain-English explanations of why they matter
* **PR-ready remediation diffs** for specific vulnerabilities

AURA is designed to *assist developers*, not replace audits or expert review.


---

## Installation

AURA currently runs as a **CLI tool**.

### Prerequisites

* Python 3.11+
* `solc` and Slither available on `PATH` (see below)

### Install AURA

Recommended — isolated CLI install via [pipx](https://pipx.pypa.io/) (requires
`pipx`: `python -m pip install --user pipx && pipx ensurepath`):

```bash
pipx install aura-audit
```

Or with pip:

```bash
pip install aura-audit
```

Either way, the installed command is `aura` — `aura-audit` is just the PyPI
distribution name (`aura` was already taken by an unrelated project).

### Install solc and Slither

AURA's analyzers shell out to `solc` and Slither, which are not bundled with
the pip package and need to be on `PATH` separately:

```bash
pipx install solc-select
solc-select install 0.8.20
solc-select use 0.8.20

pipx install slither-analyzer
```

### Contributing / running from source

```bash
poetry install
poetry run aura --help
```

---

## GitHub Action

Run AURA on every pull request: findings land in the Security tab via SARIF,
a summary comment lands on the PR, and (optionally) verified fixes land as
their own PR.

```yaml
name: aura

on:
  pull_request:

permissions:
  contents: write        # needed only for auto-fix PRs; use `read` otherwise
  security-events: write # SARIF upload
  pull-requests: write   # PR comment + fix PR

jobs:
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0   # required — AURA diffs against the PR base

      - uses: bhavi-g/AURA@main
        with:
          path: contracts
          solc-version: "0.8.20"
          fail-on: high
          # Optional: enables PRs containing AURA-verified fixes
          llm-provider: anthropic
          llm-api-key: ${{ secrets.ANTHROPIC_API_KEY }}
```

### Inputs

| Input | Default | Description |
|---|---|---|
| `path` | `.` | Path to analyze |
| `solc-version` | `0.8.20` | Compiler version installed via `solc-select` |
| `aura-version` | `""` | Empty installs the latest PyPI release; a version string pins that release; `local` installs from the caller's checkout (for testing an unreleased fix or a fork) |
| `github-token` | `${{ github.token }}` | Token for PR comments and fix PRs |
| `fail-on` | `high` | Fail on findings at/above this severity; `none` disables |
| `llm-provider` | — | `anthropic` or `openai`; required for fix PRs |
| `llm-api-key` | — | API key for that provider |
| `open-fix-prs` | `true` | Open a PR with verified fixes (no-op without a key) |

### Outputs

`findings-count`, `score`, `sarif-path`.

### Notes

- **`fetch-depth: 0` is required.** Without it AURA cannot diff against the PR
  base, and the comment falls back to listing every finding.
- **Fix PRs contain only `VERIFIED` fixes** — applied, compiled, and
  re-analyzed with the finding confirmed gone. Unverified suggestions are
  never opened as a PR.
- **Fix PRs are skipped on pull requests from forks.** GitHub issues a
  read-only token there, so the fix branch cannot be pushed.

---

## Basic Usage

### 1️⃣ Analyze a contract

Detect vulnerabilities and get a summary score.

```bash
poetry run aura analyze contracts/Reentrancy.sol
```

Example output:

```
Findings: 3 | Score: 8.3
```

---

### 2️⃣ Explain findings (human-readable)

Summarize and prioritize the most important issues.

```bash
poetry run aura explain contracts/Reentrancy.sol
```

Example:

```
Found 3 issue(s). Here are the top 3:
1. [HIGH] reentrancy-eth
2. [LOW] low-level-calls
3. [LOW] solc-version
```

---

### 3️⃣ Explain + suggest fixes (LLM-assisted)

Generate explanations **plus remediation guidance**.

```bash
poetry run aura explain-llm contracts/Reentrancy.sol --fixes
```

What this does:

* Explains exploit impact
* Describes why the issue is dangerous
* Suggests a concrete fix pattern
* Outputs a patch-style diff

---

### 4️⃣ Generate a PR-ready diff for one issue

Produce **diff-only output** suitable for direct review.

```bash
poetry run aura fix contracts/RealWorldModern.sol --rule reentrancy-eth
```

Example output:

```diff
--- contracts/RealWorldModern.sol
+++ contracts/RealWorldModern.sol
@@ -15,8 +15,8 @@
 balances[msg.sender] -= amount;
 (bool ok, ) = payable(msg.sender).call{value: amount}("");
 require(ok, "ETH transfer failed");
```

---

## Example Workflow (recommended)

```bash
# Detect issues
poetry run aura analyze contracts/MyContract.sol

# Understand the most important ones
poetry run aura explain contracts/MyContract.sol

# Generate a fix for a specific rule
poetry run aura fix contracts/MyContract.sol --rule reentrancy-eth
```

---

## Limitations (important)

* AURA **does not replace** professional audits or formal verification
* Generated diffs are **best-effort suggestions**
* All fixes should be **reviewed by a developer**
* Results depend on underlying static analyzers

AURA is meant to **reduce friction**, not eliminate responsibility.

---

## Project Status

* Early-stage developer tool
* CLI-only (UI planned later)
* Actively evolving

Feedback, issues, and contributions are welcome.

---

## License

MIT


