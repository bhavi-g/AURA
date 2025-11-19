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


def _sort_key(f: dict[str, Any]) -> tuple[float, int]:
    """Sort by score desc, then severity, then rule_id for stability."""
    score = float(f.get("score", 0) or 0)
    sev = str(f.get("severity", "")).upper()
    sev_rank = SEVERITY_ORDER.get(sev, 0)
    return (-score, -sev_rank, f.get("rule_id", "") or "")


def summarize_findings(
    findings: Iterable[dict[str, Any]],
    max_items: int = 3,
) -> str:
    """
    Produce a simple human-readable explanation of the top findings.

    This is used by both the CLI (`aura explain`) and the API (`POST /explain`).
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
        title = f.get("title", "")
        short_desc = (f.get("description") or "").splitlines()[0].strip()

        lines.append(f"{idx}. [{sev}] {rule} (score={score}): " f"{title or short_desc}")

    return "\n".join(lines)


def build_llm_explanation_prompt(
    findings: Iterable[dict[str, Any]],
    max_items: int = 3,
) -> str:
    """
    Build a prompt for the LLM that includes a short deterministic summary
    plus structured data for the top findings.

    This is used by the CLI command `aura explain-llm`.
    """
    findings_list = list(findings)

    if not findings_list:
        return (
            "You are an expert smart contract auditor.\n"
            "The static analyzers did not find any issues in this contract.\n"
            "Explain briefly that no critical issues were detected and mention "
            "that this does not guarantee the absence of vulnerabilities."
        )

    # Reuse the same sorting as summarize_findings
    sorted_findings = sorted(findings_list, key=_sort_key)
    top = sorted_findings[: max(1, max_items)]

    # Human-readable summary (deterministic)
    summary_text = summarize_findings(top, max_items=max_items)

    # Build a compact structured view for the model
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
        lines.append(
            f"- rule={rule} severity={sev} score={score} "
            f"path={path}:{start_line} title={title} desc={desc}"
        )

    structured = "\n".join(lines)

    prompt = f"""
You are an expert smart contract security auditor.

The AURA static analyzers have produced the following top findings:

Summary:
{summary_text}

Structured findings:
{structured}

Write a clear, concise explanation (aim for 2–4 short paragraphs) that:
- Highlights the most critical risks first
- Explains the impact in simple language suitable for a developer
- Mentions any assumptions or limitations of static analysis
- Suggests 1–2 concrete next steps for remediation and further review

Do not invent findings that are not listed above.
"""
    return prompt.strip()


async def async_explain_target_with_llm(
    target: str,
    project: str = "default",
    max_items: int = 3,
) -> str:
    """
    Convenience helper for async contexts (API / workers).

    - Runs the static analysis pipeline on `target`
    - Builds an LLM prompt from the findings
    - Asks the LLM for a natural-language explanation
    """
    # Local imports to avoid circular import issues at module import time
    from aura.core.llm import LLM
    from aura.core.pipeline import run_analysis

    res = run_analysis(target, project_name=project)
    findings = res.get("findings", [])

    prompt = build_llm_explanation_prompt(findings, max_items=max_items)
    llm = LLM()
    return await llm.acomplete(prompt)
