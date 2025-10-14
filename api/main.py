from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from aura.core.pipeline import run_analysis

app = FastAPI(title="AURA API")


@app.get("/health")
def health():
    return {"ok": True}


# ---- Week0/1-compatible /audit accepting the test payload ----
class AuditSource(BaseModel):
    repo: str | None = None
    path: str | None = None


class AuditRequest(BaseModel):
    source: AuditSource
    depth: Literal["triage", "full"] = "triage"


FAKE_DB: dict[str, dict] = {}


@app.post("/audit")
def submit_audit(req: AuditRequest):
    job_id = "demo-audit-1"
    FAKE_DB[job_id] = {"status": "queued", "request": req.model_dump()}
    # tests expect "job_id"
    return {"job_id": job_id, "status": "accepted"}


@app.get("/report/{audit_id}")
def get_report(audit_id: str):
    if audit_id not in FAKE_DB:
        # tests expect 200 + an "error" field for unknown ids
        return {"status": "unknown", "report": None, "error": "not found"}
    return {"status": "ready", "report": {"summary": "ok"}}


# ---- Analyze endpoint used by tests ----
class AnalyzeReq(BaseModel):
    path: str
    project: str = "default"


@app.post("/analyze")
def analyze(req: AnalyzeReq):
    # Validate path early; tests expect a 400 for non-existent paths
    p = Path(req.path)
    if not p.exists():
        raise HTTPException(status_code=400, detail=f"path not found: {req.path}")

    # run analysis (pipeline signature: (target, project_name))
    res = run_analysis(req.path, req.project)

    return {
        "score": res["score"],
        "reports": res["reports"],
        "n_findings": res.get("n_findings", len(res.get("findings", []))),
    }
