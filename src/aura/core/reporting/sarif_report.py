import json
from pathlib import Path


def write_sarif(findings, out_path="reports/summary.sarif"):
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    results = []
    sev_map = {"HIGH": "error", "MEDIUM": "warning", "LOW": "note", "INFO": "note"}
    for f in findings:
        loc = (f.get("locations") or [{}])[0]
        results.append(
            {
                "ruleId": f.get("rule_id", "unknown"),
                "level": sev_map.get(f.get("severity", "LOW"), "note"),
                "message": {"text": f.get("description", "")},
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": loc.get("file", "")},
                            "region": {"startLine": loc.get("line", 0)},
                        }
                    }
                ],
                "properties": {"score": f.get("score", 0), "tool": f.get("tool", "")},
            }
        )

    sarif = {
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {"name": "AURA", "informationUri": "https://github.com/bhavi-g/AURA"}
                },
                "results": results,
            }
        ],
    }
    Path(out_path).write_text(json.dumps(sarif, indent=2))
    return str(Path(out_path).resolve())
