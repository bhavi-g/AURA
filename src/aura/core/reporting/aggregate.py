from __future__ import annotations

import collections
import json
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

Finding = dict[str, Any]


def write_index_md(
    findings: Iterable[Finding], score: float | int | None, out_path: str = "reports/index.md"
) -> str:
    findings = list(findings or [])
    by_cat = collections.Counter(f.get("category", "Unknown") for f in findings)
    by_rule = collections.Counter(f.get("rule_id", "unknown") for f in findings)
    by_sev = collections.Counter(f.get("severity", "LOW") for f in findings)

    def md_table(counter, left, right):
        rows = [f"| {left} | {right} |", "|---|---|"]
        rows += [f"| `{k}` | {v} |" for k, v in counter.most_common()]
        return "\n".join(rows)

    lines = []
    lines.append("# AURA Report (Week 3)")
    lines.append(f"- Generated: {datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"- Findings: **{len(findings)}**")
    if isinstance(score, (int, float)):
        lines.append(f"- Score: **{score:.2f}**")
    lines.append("")
    lines.append("## Severity Breakdown")
    lines.append(md_table(by_sev, "Severity", "Count"))
    lines.append("")
    lines.append("## Category Breakdown")
    lines.append(md_table(by_cat, "Category", "Count"))
    lines.append("")
    lines.append("## Top Rules")
    lines.append(md_table(by_rule, "Rule ID", "Hits"))
    lines.append("")
    lines.append("## Sample Findings (first 10)")
    lines.append("| Rule | Severity | File:Line | Title |")
    lines.append("|---|---|---|---|")
    for f in findings[:10]:
        loc = (f.get("locations") or [{"file": "?", "line": 1}])[0]
        lines.append(
            f"| `{f.get('rule_id')}` | {f.get('severity','')}"
            f" | {loc.get('file')}:{loc.get('line')} | {f.get('title','')} |"
        )

    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(lines))
    return str(p)


def load_parsed_and_score(reports_dir: str = "reports") -> tuple[list[Finding], float | None]:
    rd = Path(reports_dir)
    findings = (
        json.loads((rd / "slither_parsed.json").read_text())
        if (rd / "slither_parsed.json").exists()
        else []
    )
    score = None
    if (rd / "summary.json").exists():
        try:
            score = json.loads((rd / "summary.json").read_text()).get("score")
        except Exception:
            score = None
    return findings, score
