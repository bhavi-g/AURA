# src/aura/core/analyzers/mythril_adapter.py
import json
import shlex
import subprocess

from .normalize import Finding

_SEV = {"low": "LOW", "medium": "MEDIUM", "high": "HIGH", "critical": "CRITICAL"}


class MythrilAnalyzer:
    name = "mythril"

    def run(self, target: str) -> list[Finding]:
        """
        Run Mythril via CLI and normalize its JSON output.

        Notes:
        - Uses subprocess to avoid importing mythril's Python package (version conflicts).
        - Timeout keeps runs bounded for CI/dev.
        """
        cmd = f"myth analyze {shlex.quote(target)} -o json --execution-timeout 20 --max-depth 12"
        try:
            out = subprocess.check_output(
                cmd, shell=True, text=True, stderr=subprocess.STDOUT, timeout=120
            )
        except subprocess.CalledProcessError as e:
            # myth returns non-zero for findings; still try to parse stdout
            out = e.output or ""
        except subprocess.TimeoutExpired:
            return []

        try:
            data = json.loads(out)
        except json.JSONDecodeError:
            return []

        issues = []
        # Mythril JSON usually has {"issues": [...]}; be defensive
        root = data if isinstance(data, dict) else {}
        for it in root.get("issues", []):
            sev = _SEV.get(str(it.get("severity", "")).lower(), "LOW")
            title = it.get("title") or it.get("description-head") or "Mythril issue"
            desc = (
                " ".join(x for x in [it.get("description-head"), it.get("description-tail")] if x)
                or it.get("description")
                or ""
            )
            rule = it.get("swc-id") or it.get("check") or "SWC-000"
            category = rule if isinstance(rule, str) else "Unknown"

            # locations: Mythril varies; try to extract a file/line
            locs = []
            for loc in it.get("locations", []):
                # try common shapes
                file = loc.get("filename") or loc.get("file") or target
                line = int(loc.get("line")) if isinstance(loc.get("line"), int) else 1
                locs.append({"file": file, "line": line})
            if not locs:
                locs = [{"file": target, "line": 1}]

            issues.append(
                {
                    "tool": "mythril",
                    "rule_id": str(rule),
                    "title": title,
                    "description": desc,
                    "severity": sev,
                    "confidence": "MEDIUM",
                    "category": str(category),
                    "locations": locs,
                    "references": [
                        u for u in it.get("externalReferences", []) if isinstance(u, str)
                    ],
                    "raw": it,
                }
            )

        return issues
