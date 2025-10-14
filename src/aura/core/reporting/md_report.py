from pathlib import Path


def write_md(findings, score, out_path="reports/summary.md"):
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Aura Analysis Summary",
        "",
        f"**Score:** {score}",
        "",
        "| Rule | Severity | Score | Location |",
        "|------|----------|-------|----------|",
    ]
    for f in findings[:50]:
        loc = f["locations"][0] if f["locations"] else {}
        fileline = f"{loc.get('file', '')}:{loc.get('line', '')}"
        lines.append(f"| {f['rule_id']} | {f['severity']} | {f.get('score', 0)} | {fileline} |")
    p.write_text("\n".join(lines))
    return str(p)
