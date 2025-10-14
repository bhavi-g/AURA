from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_analyze_missing_path_returns_422():
    r = client.post("/analyze", json={"project": "default"})
    assert r.status_code == 422
    body = r.json()
    # pydantic validation error structure
    assert isinstance(body.get("detail"), list)


def test_analyze_nonexistent_path_returns_400(tmp_path):
    bad = tmp_path / "nope.sol"
    r = client.post("/analyze", json={"path": str(bad), "project": "default"})
    # your API should validate the path and reject missing files/dirs
    # expect 400 with a meaningful error message
    assert r.status_code in (400, 404)
