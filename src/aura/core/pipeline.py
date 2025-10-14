from .analyzers.mythril_adapter import MythrilAnalyzer
from .analyzers.slither_adapter import SlitherAnalyzer
from .persistence import crud
from .reporting.json_report import write_json
from .reporting.md_report import write_md
from .scoring.rules_v0 import aggregate_score, score_finding


def run_analysis(target: str, project_name: str):
    tools = [SlitherAnalyzer(), MythrilAnalyzer()]
    all_findings = []
    for t in tools:
        findings = t.run(target)
        for f in findings:
            f["score"] = score_finding(f)
        all_findings.extend(findings)
    project, artifact, run = crud.ensure_entities(
        project_name, target, tools=[t.name for t in tools]
    )
    crud.save_findings(run.id, all_findings)
    score = aggregate_score(all_findings)
    j = write_json(all_findings, score)
    m = write_md(all_findings, score)
    return {
        "project_id": project.id,
        "findings": all_findings,
        "score": score,
        "reports": {"json": j, "md": m},
    }
