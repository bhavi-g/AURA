import pytest


@pytest.fixture
def temp_cwd(tmp_path, monkeypatch):
    # Run each test in a clean working dir so .aura/ and reports/ are isolated
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def sample_contract(temp_cwd):
    src = """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract ReentrancyDemo {
    mapping(address => uint256) public balances;

    function deposit() external payable { balances[msg.sender] += msg.value; }

    function withdraw() external {
        uint256 amount = balances[msg.sender];
        (bool ok,) = msg.sender.call{value: amount}("");
        require(ok, "send failed");
        balances[msg.sender] = 0;
    }
}
"""
    contracts = temp_cwd / "contracts"
    contracts.mkdir(exist_ok=True)
    path = contracts / "ReentrancyDemo.sol"
    path.write_text(src)
    return path


@pytest.fixture
def fake_slither_findings():
    # Minimal fixture shaped like your normalized SlitherAdapter output
    return [
        {
            "tool": "slither",
            "rule_id": "reentrancy-eth",
            "title": "reentrancy-eth",
            "description": "Reentrancy in withdraw()",
            "severity": "HIGH",
            "confidence": "MEDIUM",
            "category": "reentrancy-eth",
            "locations": [
                {"file": "contracts/ReentrancyDemo.sol", "line": 11, "function": "withdraw"}
            ],
            "references": [],
            "raw": {},
            "score": 5.1,
        },
        {
            "tool": "slither",
            "rule_id": "solc-version",
            "title": "solc-version",
            "description": "pragma ^0.8.20",
            "severity": "LOW",
            "confidence": "HIGH",
            "category": "solc-version",
            "locations": [
                {"file": "contracts/ReentrancyDemo.sol", "line": 2, "function": "^0.8.20"}
            ],
            "references": [],
            "raw": {},
            "score": 1.0,
        },
        {
            "tool": "slither",
            "rule_id": "low-level-calls",
            "title": "low-level-calls",
            "description": "low-level call",
            "severity": "LOW",
            "confidence": "HIGH",
            "category": "low-level-calls",
            "locations": [
                {"file": "contracts/ReentrancyDemo.sol", "line": 14, "function": "withdraw"}
            ],
            "references": [],
            "raw": {},
            "score": 1.0,
        },
    ]
