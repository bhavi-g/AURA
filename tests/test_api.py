from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_submit_audit():
    payload = {"source": {"repo": "https://example.com/repo.git"}, "depth": "triage"}
    r = client.post("/audit", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert "job_id" in data


def test_report_unknown():
    r = client.get("/report/does-not-exist")
    assert r.status_code == 200
    assert "error" in r.json()
