import json

from sqlmodel import select

from .db import get_session, init_db
from .models import Artifact
from .models import Finding as FModel
from .models import Project, Run


def ensure_entities(
    project_name: str, target: str, tools: list[str]
) -> tuple[Project, Artifact, Run]:
    init_db()
    with get_session() as s:
        proj = s.exec(select(Project).where(Project.name == project_name)).one_or_none()
        if not proj:
            proj = Project(name=project_name)
            s.add(proj)
            s.commit()
            s.refresh(proj)
        art = Artifact(project_id=proj.id, kind="solidity", path=target)
        s.add(art)
        s.commit()
        s.refresh(art)
        run = Run(artifact_id=art.id, tool=",".join(tools))
        s.add(run)
        s.commit()
        s.refresh(run)
        return proj, art, run


def save_findings(run_id: int, findings: list[dict]):
    with get_session() as s:
        for f in findings:
            rec = FModel(
                run_id=run_id,
                tool=f["tool"],
                rule_id=f["rule_id"],
                title=f["title"],
                severity=f["severity"],
                confidence=f["confidence"],
                category=f["category"],
                score=f.get("score", 0.0),
                data=json.dumps(f),
            )
            s.add(rec)
        s.commit()
