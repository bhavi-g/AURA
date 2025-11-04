import json
from pathlib import Path

from aura.core.evaluation.evaluator import evaluate


def _mk_sarif(tmp: Path, results) -> Path:
    sarif = {
        "runs": [{"tool": {"driver": {"rules": [{"id": "solc-version"}]}}, "results": results}]
    }
    p = tmp / "r.sarif"
    p.write_text(json.dumps(sarif))
    return p


def test_eval_basic(tmp_path: Path) -> None:
    gold = _mk_sarif(
        tmp_path,
        [
            {
                "ruleId": "solc-version",
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": "a.sol"},
                            "region": {"startLine": 2},
                        }
                    }
                ],
            }
        ],
    )
    pred = _mk_sarif(
        tmp_path,
        [
            {
                "ruleId": "solc-version",
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": "a.sol"},
                            "region": {"startLine": 2},
                        }
                    }
                ],
            }
        ],
    )
    m = evaluate(pred, gold)
    assert m["tp"] == 1 and m["fp"] == 0 and m["fn"] == 0
    assert m["f1"] == 1.0
