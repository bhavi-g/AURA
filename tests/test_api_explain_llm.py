# tests/test_api_explain_llm.py

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_explain_llm_missing_path():
    resp = client.post(
        "/explain-llm",
        json={
            "path": "this/does/not/exist.sol",
            "project": "default",
            "max_items": 3,
        },
    )
    assert resp.status_code == 400
    data = resp.json()
    assert "path not found" in data["detail"]


def test_explain_llm_with_real_contract():
    """
    Use one of the sample contracts in the repo.

    We try a few likely locations and skip the test gracefully if none exist,
    so the test suite doesn't become brittle to small path changes.
    """
    candidate_paths = [
        Path("contracts/Reentrancy.sol"),
        Path("samples/contracts/Reentrancy.sol"),
        Path("samples/contracts/contracts/Reentrancy.sol"),
    ]

    contract_path: Path | None = None
    for p in candidate_paths:
        if p.exists():
            contract_path = p
            break

    if contract_path is None:
        pytest.skip("No Reentrancy.sol contract found in expected paths")

    resp = client.post(
        "/explain-llm",
        json={
            "path": str(contract_path),
            "project": "default",
            "max_items": 3,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "explanation" in data
    assert isinstance(data["explanation"], str)
    # In stub mode, should mention LLM STUB.
    assert "[LLM STUB]" in data["explanation"]
