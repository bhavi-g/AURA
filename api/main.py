from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel

from aura.core.pipeline import run_analysis  # <-- uses your new pipeline

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


class AnalyzeReq(BaseModel):
    path: str
    project: str = "default"


@app.post("/analyze")
def analyze(req: AnalyzeReq):
    res = run_analysis(req.path, project_name=req.project)
    return {"score": res["score"], "reports": res["reports"], "n_findings": len(res["findings"])}
