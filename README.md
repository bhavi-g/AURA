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

* Python 3.10+
* Poetry
* `solc` available in PATH
* Slither installed

### Install dependencies

```bash
poetry install
```

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


