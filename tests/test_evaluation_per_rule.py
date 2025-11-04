import json
from pathlib import Path

from aura.core.evaluation.evaluator import evaluate


def _mk_sarif(path: Path, results, name: str) -> Path:
    sarif = {
        "runs": [
            {
                "tool": {"driver": {"rules": [{"id": "solc-version"}, {"id": "reentrancy-eth"}]}},
                "results": results,
            }
        ]
    }
    p = path / name
    p.write_text(json.dumps(sarif))
    return p


def test_per_rule_metrics(tmp_path: Path) -> None:
    # Gold: 2 findings for solc-version, 1 for reentrancy-eth
    gold = _mk_sarif(
        tmp_path,
        [
            {
                "ruleId": "solc-version",
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": "A.sol"},
                            "region": {"startLine": 2},
                        }
                    }
                ],
            },
            {
                "ruleId": "solc-version",
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": "B.sol"},
                            "region": {"startLine": 2},
                        }
                    }
                ],
            },
            {
                "ruleId": "reentrancy-eth",
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": "C.sol"},
                            "region": {"startLine": 6},
                        }
                    }
                ],
            },
        ],
        name="gold.sarif",
    )
    # Pred: 1 matching solc-version, 1 FP for reentrancy-eth, and miss one solc-version
    pred = _mk_sarif(
        tmp_path,
        [
            {
                "ruleId": "solc-version",
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": "A.sol"},
                            "region": {"startLine": 2},
                        }
                    }
                ],
            },  # TP
            {
                "ruleId": "reentrancy-eth",
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": "D.sol"},
                            "region": {"startLine": 6},
                        }
                    }
                ],
            },  # FP
        ],
        name="pred.sarif",
    )

    m = evaluate(pred, gold)
    # Overall:
    # - solc-version: 2 gold, 1 pred -> TP=1, FN=1
    # - reentrancy-eth: 1 gold, 1 pred (wrong file) -> TP=0, FP=1, FN=1
    assert m["tp"] == 1 and m["fp"] == 1 and m["fn"] == 2
    assert "by_rule" in m

    sr = m["by_rule"]["solc-version"]
    assert sr["tp"] == 1 and sr["fp"] == 0 and sr["fn"] == 1
    rr = m["by_rule"]["reentrancy-eth"]
    assert rr["tp"] == 0 and rr["fp"] == 1 and rr["fn"] == 1

    # sanity on rounding & bounds
    for k in ("precision", "recall", "f1"):
        assert 0.0 <= sr[k] <= 1.0
        assert 0.0 <= rr[k] <= 1.0
