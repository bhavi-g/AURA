# src/aura/core/analyzers/slither_adapter.py
from __future__ import annotations

import json
import re
import shlex
import shutil
import subprocess

# If you have a Finding TypedDict, import it; otherwise we’ll return dicts.
# from .normalize import Finding

Finding = dict  # keep it simple/compatible


def _run_cmd(cmd: str, timeout: int = 120) -> str:
    try:
        return subprocess.check_output(
            cmd, shell=True, text=True, stderr=subprocess.STDOUT, timeout=timeout
        )
    except subprocess.CalledProcessError as e:
        # Slither may return non-zero when findings exist; still parse stdout
        return e.output or ""
    except subprocess.TimeoutExpired:
        return ""


def _extract_json_block(text: str) -> str:
    """
    Slither with --json - should print raw JSON, but wrappers (e.g. pipx) can
    prepend banners. This extracts the last {...} block safely.
    """
    if not text:
        return ""
    # Quick path: already clean JSON
    s = text.strip()
    if s.startswith("{") and s.endswith("}"):
        return s
    # Fallback: grab the last balanced JSON object
    m = re.search(r"\{(?:.|\n)*\}\s*$", text)
    return m.group(0) if m else ""


class SlitherAnalyzer:
    name = "slither"

    def run(self, target: str) -> list[Finding]:
        """
        Run Slither and normalize output to a list of Finding dicts.
        """
        cmds: list[str] = []

        # Prefer a real slither on PATH (your venv one)
        if shutil.which("slither"):
            cmds.append(f"slither {shlex.quote(target)} --json -")

        # pipx fallback (isolated env) — sometimes prints banners before JSON
        cmds.append(f"pipx run --spec slither-analyzer slither {shlex.quote(target)} --json -")

        raw_out = ""
        for cmd in cmds:
            raw_out = _run_cmd(cmd)
            if raw_out.strip():
                break

        # --- STEP 2: dump raw output for debugging ---
        try:
            import os

            os.makedirs("reports", exist_ok=True)
            with open("reports/slither_raw.txt", "w") as fh:
                fh.write(raw_out or "")
        except Exception:
            pass
        # --------------------------------------------

        if not raw_out.strip():
            return []

        json_text = _extract_json_block(raw_out)
        if not json_text:
            return []

        try:
            data = json.loads(json_text)
        except json.JSONDecodeError:
            return []

        # Slither JSON structure (v0.11.x): {"success": bool, "results": {"detectors": [...]}}
        results = (data or {}).get("results", {})
        detectors = results.get("detectors", []) or []
        findings: list[Finding] = []

        for item in detectors:
            sev = (item.get("impact") or "LOW").upper()
            conf = (item.get("confidence") or "LOW").upper()
            title = item.get("check", "slither-issue")
            desc = item.get("description") or item.get("markdown") or ""
            rule_id = item.get("check", "slither-issue")
            category = str(rule_id).split(":")[0] if isinstance(rule_id, str) else "Unknown"

            locs = []
            for e in item.get("elements", []):
                src = e.get("source_mapping") or {}
                filename = src.get("filename_relative") or src.get("filename") or target
                lines = src.get("lines") or []
                line = int(lines[0]) if isinstance(lines, list) and lines else 1
                locs.append({"file": filename, "line": line, "function": e.get("name")})

            findings.append(
                {
                    "tool": "slither",
                    "rule_id": rule_id,
                    "title": title,
                    "description": desc,
                    "severity": sev if sev in {"LOW", "MEDIUM", "HIGH", "CRITICAL"} else "LOW",
                    "confidence": conf if conf in {"LOW", "MEDIUM", "HIGH"} else "LOW",
                    "category": category,
                    "locations": locs or [{"file": target, "line": 1}],
                    "references": [
                        v for v in (item.get("documentation") or {}).values() if isinstance(v, str)
                    ],
                    "raw": item,
                }
            )

        # Optional: also dump our normalized findings for quick inspection
        try:
            with open("reports/slither_parsed.json", "w") as fh:
                json.dump(findings, fh, indent=2)
        except Exception:
            pass

        return findings
