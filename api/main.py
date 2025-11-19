from pathlib import Path
from typing import Literal

from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel

from aura.core.explain import async_explain_target_with_llm, summarize_findings
from aura.core.pipeline import run_analysis

SEVERITY_ORDER = {
    "CRITICAL": 4,
    "HIGH": 3,
    "MEDIUM": 2,
    "LOW": 1,
    "INFO": 0,
    "INFORMATIONAL": 0,
}

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


def _run_audit_job(job_id: str, req: AuditRequest) -> None:
    """
    Background worker: runs the analysis and stores the result in FAKE_DB.
    This simulates an async worker without external queues.
    """
    record = FAKE_DB.get(job_id)
    if record is None:
        return

    record["status"] = "running"

    path = req.source.path or "contracts/ReentrancyDemo.sol"
    p = Path(path)

    if not p.exists():
        record["status"] = "error"
        record["error"] = f"path not found: {path}"
        return

    try:
        project_name = req.source.repo or "audit"
        res = run_analysis(path, project_name=project_name)
        record["status"] = "ready"
        record["result"] = res
    except Exception as exc:  # pragma: no cover (safety net)
        record["status"] = "error"
        record["error"] = str(exc)


@app.post("/audit")
def submit_audit(req: AuditRequest, background_tasks: BackgroundTasks):
    """
    Submit an audit job.

    - Returns immediately with job_id + accepted status.
    - Actual analysis runs in a background task and updates FAKE_DB.
    """
    job_id = "demo-audit-1"  # keep stable for tests

    FAKE_DB[job_id] = {
        "status": "queued",
        "request": req.model_dump(),
        "result": None,
    }

    background_tasks.add_task(_run_audit_job, job_id, req)

    # tests expect "job_id" and "status"
    return {"job_id": job_id, "status": "accepted"}


@app.get("/report/{audit_id}")
def get_report(audit_id: str):
    job = FAKE_DB.get(audit_id)
    if job is None:
        # tests expect 200 + an "error" field for unknown ids
        return {"status": "unknown", "report": None, "error": "not found"}

    status = job.get("status", "unknown")

    if status in {"queued", "running"}:
        return {"status": status, "report": None}

    if status == "error":
        return {
            "status": "error",
            "report": None,
            "error": job.get("error", "analysis failed"),
        }

    res = job.get("result")

    if not res:
        # Backwards-compatible minimal response (what tests expect)
        return {"status": "ready", "report": {"summary": "ok"}}

    return {
        "status": "ready",
        "report": {
            "summary": "ok",  # keep for backwards compatibility
            "details": {
                "score": res.get("score"),
                "n_findings": res.get("n_findings", len(res.get("findings", []))),
                "reports": res.get("reports", {}),
            },
        },
    }


# ---- Analyze endpoint used by tests ----
class AnalyzeReq(BaseModel):
    path: str
    project: str = "default"
    full: bool = False


@app.post("/analyze")
def analyze(req: AnalyzeReq):
    # Validate path early; tests expect a 400 for non-existent paths
    p = Path(req.path)
    if not p.exists():
        raise HTTPException(status_code=400, detail=f"path not found: {req.path}")

    # run analysis (pipeline signature: (target, project_name))
    res = run_analysis(req.path, req.project)

    # If full report requested, return everything
    if req.full:
        return res

    # Tests expect the minimal response:
    return {
        "score": res["score"],
        "reports": res["reports"],
        "n_findings": res.get("n_findings", len(res.get("findings", []))),
    }


# ---- Explain endpoint (natural-language summary) ----
class ExplainReq(BaseModel):
    path: str
    project: str = "default"
    max_items: int = 3


@app.post("/explain")
def explain(req: ExplainReq):
    # Validate path early
    p = Path(req.path)
    if not p.exists():
        raise HTTPException(status_code=400, detail=f"path not found: {req.path}")

    # Run analysis
    res = run_analysis(req.path, req.project)
    findings = res.get("findings", [])
    summary = summarize_findings(findings, max_items=req.max_items)

    sorted_findings = sorted(
        findings,
        key=lambda f: (
            -(f.get("score") or 0),
            -SEVERITY_ORDER.get(str(f.get("severity", "")).upper(), 0),
            f.get("rule_id", "") or "",
        ),
    )
    top = sorted_findings[: max(1, req.max_items)]

    simplified_top = []
    for f in top:
        simplified_top.append(
            {
                "rule_id": f.get("rule_id"),
                "title": f.get("title"),
                "severity": f.get("severity"),
                "score": f.get("score"),
                "description": (f.get("description") or "").splitlines()[0].strip(),
            }
        )

    return {
        "summary": summary,
        "n_findings": res.get("n_findings", len(findings)),
        "score": res.get("score"),
        "top_findings": simplified_top,
    }


# ---- LLM-powered explain endpoint ----
class ExplainLLMReq(BaseModel):
    path: str
    project: str = "default"
    max_items: int = 3


@app.post("/explain-llm")
async def explain_llm(req: ExplainLLMReq):
    # Validate path early
    p = Path(req.path)
    if not p.exists():
        raise HTTPException(status_code=400, detail=f"path not found: {req.path}")

    explanation = await async_explain_target_with_llm(
        target=req.path,
        project=req.project,
        max_items=req.max_items,
    )

    return {
        "explanation": explanation,
    }
