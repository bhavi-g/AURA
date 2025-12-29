from __future__ import annotations

from collections.abc import Iterable
from typing import Any

SEVERITY_ORDER = {
    "CRITICAL": 4,
    "HIGH": 3,
    "MEDIUM": 2,
    "LOW": 1,
    "INFO": 0,
    "INFORMATIONAL": 0,
}


def _sort_key(f: dict[str, Any]) -> tuple[float, int, str]:
    """Sort by score desc, then severity, then rule_id for stability."""
    score = float(f.get("score", 0) or 0)
    sev = str(f.get("severity", "")).upper()
    sev_rank = SEVERITY_ORDER.get(sev, 0)
    rule_id = str(f.get("rule_id", "") or "")
    return (-score, -sev_rank, rule_id)


def summarize_findings(
    findings: Iterable[dict[str, Any]],
    max_items: int = 3,
) -> str:
    """
    Produce a simple human-readable explanation of the top findings.

    Used by CLI (`aura explain`) and API (`POST /explain`).
    """
    findings_list = list(findings)

    if not findings_list:
        return "No issues detected. The contract looks clean under the current analyzers."

    sorted_findings = sorted(findings_list, key=_sort_key)
    top = sorted_findings[: max(1, max_items)]

    lines: list[str] = []
    lines.append(f"Found {len(findings_list)} issue(s). Here are the top {len(top)}:")

    for idx, f in enumerate(top, start=1):
        rule = f.get("rule_id", "unknown-rule")
        sev = str(f.get("severity", "UNKNOWN")).upper()
        score = f.get("score", 0)
        title = f.get("title", "") or ""
        short_desc = (f.get("description") or "").splitlines()[0].strip()
        lines.append(f"{idx}. [{sev}] {rule} (score={score}): {title or short_desc}")

    return "\n".join(lines)


def build_llm_explanation_prompt(
    findings: Iterable[dict[str, Any]],
    max_items: int = 3,
) -> str:
    """
    Build a prompt for the LLM: short deterministic summary + structured view.

    Used by `aura explain-llm` (without --fixes).
    """
    findings_list = list(findings)

    if not findings_list:
        return (
            "You are an expert smart contract security auditor.\n"
            "The static analyzers did not find any issues in this contract.\n"
            "Explain briefly that no critical issues were detected and mention "
            "that this does not guarantee the absence of vulnerabilities."
        )

    sorted_findings = sorted(findings_list, key=_sort_key)
    top = sorted_findings[: max(1, max_items)]

    summary_text = summarize_findings(top, max_items=max_items)

    lines: list[str] = []
    for f in top:
        rule = f.get("rule_id", "unknown-rule")
        sev = str(f.get("severity", "UNKNOWN")).upper()
        score = f.get("score", 0)
        title = f.get("title") or ""
        desc = (f.get("description") or "").strip().replace("\n", " ")
        loc = f.get("location") or {}
        path = loc.get("path", "")
        start_line = loc.get("start_line", "")
        end_line = loc.get("end_line", "")
        func = loc.get("function", "") or loc.get("symbol", "")
        where = f"{path}:{start_line}-{end_line}"
        if func:
            where += f" ({func})"
        lines.append(
            f"- rule={rule} severity={sev} score={score} where={where} title={title} desc={desc}"
        )

    structured = "\n".join(lines)

    prompt = f"""
You are an expert smart contract security auditor.

You will be given ONLY the findings below. Do not invent additional vulnerabilities.
If you are unsure about something, say so.

Findings summary:
{summary_text}

Structured findings:
{structured}

Write a clear, concise explanation (2–4 short paragraphs) that:
- Highlights the most critical risks first
- Explains impact in developer-friendly terms
- Mentions limitations of static analysis
- Suggests 1–2 concrete next steps

Do not invent findings not listed above.
"""
    return prompt.strip()


def build_llm_remediation_prompt(
    findings: Iterable[dict[str, Any]],
    max_items: int = 3,
) -> str:
    """
    Build an LLM prompt that asks for explanations + concrete fix suggestions
    and a diff-style patch.

    Used by `aura explain-llm --fixes`.
    """
    findings_list = list(findings)

    if not findings_list:
        return (
            "You are an expert smart contract security auditor.\n\n"
            "The static analyzers found no issues in this contract. "
            "Confirm that there are no obvious security problems and briefly mention "
            "general best practices."
        )

    sorted_findings = sorted(findings_list, key=_sort_key)
    top = sorted_findings[: max(1, max_items)]

    summary_text = summarize_findings(top, max_items=max_items)

    items: list[str] = []
    for f in top:
        rule = f.get("rule_id", "unknown-rule")
        sev = str(f.get("severity", "UNKNOWN")).upper()
        desc = (f.get("description") or "").strip().replace("\n", " ")
        loc = f.get("location") or {}
        path = loc.get("path", "")
        start_line = loc.get("start_line", "")
        end_line = loc.get("end_line", "")
        func = loc.get("function", "") or loc.get("symbol", "")
        where = f"{path}:{start_line}-{end_line}"
        if func:
            where += f" ({func})"

        items.append(
            f"- Rule: {rule}\n"
            f"  Severity: {sev}\n"
            f"  Where: {where or 'not provided'}\n"
            f"  Description: {desc}"
        )

    issues_block = "\n".join(items)

    prompt = f"""
You are an expert smart contract security auditor.

Use ONLY the issues listed below. Do NOT invent vulnerabilities.
Do NOT claim compiler versions are unsafe unless explicitly stated in the finding text.

Summary:
{summary_text}

Issues:
{issues_block}

For EACH issue, respond using EXACTLY this format:

Issue: <short name>
Severity: <level>
Where: <location or 'not provided'>
Why it matters: <1–2 sentences>
Exploit scenario:
- <1–3 bullets>

Recommended fix:
- <2–5 concrete, code-oriented steps>

Patch (diff):
[diff]
<best-effort minimal patch or pseudo-diff if code context is missing>
[/diff]

Confidence: <High/Medium/Low>
"""
    return prompt.strip()


async def async_explain_target_with_llm(
    target: str,
    project: str = "default",
    max_items: int = 3,
) -> str:
    """
    Convenience helper for async contexts (API / workers).

    - Runs analysis on `target`
    - Builds an LLM prompt from findings
    - Calls the LLM for an explanation
    """
    from aura.core.llm import LLM
    from aura.core.pipeline import run_analysis

    res = run_analysis(target, project_name=project)
    findings = res.get("findings", [])

    prompt = build_llm_explanation_prompt(findings, max_items=max_items)
    llm = LLM()
    return await llm.acomplete(prompt)
