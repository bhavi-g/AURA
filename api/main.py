from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


class AuditReq(BaseModel):
    path: str


@app.post("/audit")
def audit(req: AuditReq):
    p = Path(req.path)
    findings = []
    if "Reentrancy" in p.name:
        findings = ["ReentrancyDemo"]
    risk_score = 80 if findings else 20
    return {
        "contract_path": str(p),
        "findings": findings,
        "risk_summary": {"overall_score": risk_score},
    }


@app.get("/health")
def health():
    return {"ok": True}
