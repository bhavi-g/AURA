def analyze_contract(source: dict) -> list[dict]:
    # Return ONE fake vulnerability in our schema
    return [
        {
            "id": "demo-0001",
            "swc_id": "SWC-107",
            "name": "Reentrancy (demo)",
            "severity": "HIGH",
            "probability": 0.72,
            "calibrated_probability": 0.70,
            "expected_loss": 1000.0,
            "location": {"file": "Demo.sol", "line": 42, "column": 1},
            "evidence": {
                "trace": ["CALL -> state change -> external CALL"],
                "constraints": ["msg.value > 0"],
                "snippet": "function withdraw() external { (bool ok,) = target.call(...); ... }",
            },
            "recommendation": "Use ReentrancyGuard or checks-effects-interactions.",
            "uncertainty": {"epistemic": 0.15, "aleatoric": 0.10},
        }
    ]
