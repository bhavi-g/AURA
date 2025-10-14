from fastapi.testclient import TestClient

from api.main import app


def test_api_analyze_endpoint(monkeypatch, temp_cwd, sample_contract, fake_slither_findings):
    # Mock Slither in the pipeline indirectly by patching the adapter method
    from aura.core.analyzers import slither_adapter

    monkeypatch.setattr(
        slither_adapter.SlitherAnalyzer,
        "run",
        lambda self, target: fake_slither_findings,
    )

    client = TestClient(app)
    resp = client.post("/analyze", json={"path": str(sample_contract), "project": "default"})
    assert resp.status_code == 200, resp.text

    data = resp.json()
    assert data["score"] > 0
    assert data["n_findings"] == len(fake_slither_findings)
