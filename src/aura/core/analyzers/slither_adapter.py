# src/aura/core/analyzers/slither_adapter.py
from __future__ import annotations

import json
import re
import shlex
import shutil
import subprocess
from typing import Any

Finding = dict[str, Any]  # simple, test-friendly shape


def _run_cmd(cmd: str, timeout: int = 120) -> tuple[str, str | None]:
    """Run a shell command, returning (stdout, error). error is None on a clean run."""
    try:
        out = subprocess.check_output(
            cmd, shell=True, text=True, stderr=subprocess.STDOUT, timeout=timeout
        )
        return out, None
    except subprocess.CalledProcessError as e:
        # Slither may return non-zero when findings exist; still try to parse stdout,
        # but keep the error in case there's nothing usable in the output.
        return e.output or "", f"exited {e.returncode}: {(e.output or '').strip()[-300:]}"
    except subprocess.TimeoutExpired:
        return "", f"timed out after {timeout}s"


def _extract_json_block(text: str) -> str:
    """
    Slither with --json - should print raw JSON, but wrappers (e.g. pipx) can
    prepend banners. This extracts the last {...} block safely.
    """
    if not text:
        return ""
    s = text.strip()
    if s.startswith("{") and s.endswith("}"):
        return s
    m = re.search(r"\{(?:.|\n)*\}\s*$", text)
    return m.group(0) if m else ""


class SlitherAnalyzer:
    name = "slither"

    def __init__(self) -> None:
        self.last_error: str | None = None

    def run(self, target: str) -> list[Finding]:
        """
        Run Slither and normalize output to a list of Finding dicts.

        On failure, returns [] and records the reason in `self.last_error`
        so callers can tell "no vulnerabilities found" apart from
        "the scanner didn't actually run".
        """
        self.last_error = None

        cmds: list[str] = []
        if shutil.which("slither"):
            cmds.append(f"slither {shlex.quote(target)} --json -")
        # pipx fallback (isolated env) — sometimes prints banners before JSON
        cmds.append(f"pipx run --spec slither-analyzer slither {shlex.quote(target)} --json -")

        raw_out = ""
        err: str | None = None
        for cmd in cmds:
            raw_out, err = _run_cmd(cmd)
            if raw_out.strip():
                err = None
                break

        # Dump raw output for debugging (best-effort)
        try:
            import os

            os.makedirs("reports", exist_ok=True)
            with open("reports/slither_raw.txt", "w") as fh:
                fh.write(raw_out or "")
        except Exception:
            pass

        if not raw_out.strip():
            self.last_error = err or "slither produced no output"
            return []

        json_text = _extract_json_block(raw_out)
        if not json_text:
            self.last_error = err or "slither output did not contain JSON"
            return []

        try:
            data = json.loads(json_text)
        except json.JSONDecodeError:
            self.last_error = "slither output was not valid JSON"
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

        # Also dump normalized findings (best-effort)
        try:
            with open("reports/slither_parsed.json", "w") as fh:
                json.dump(findings, fh, indent=2)
        except Exception:
            pass

        return findings
