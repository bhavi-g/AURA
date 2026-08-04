from __future__ import annotations

import json
import time
from importlib import metadata
from pathlib import Path
from typing import Annotated

import typer

from aura.core.evaluation import evaluate
from aura.core.explain import (
    build_llm_explanation_prompt,
    build_llm_remediation_prompt,
    summarize_findings,
)
from aura.core.fix import verify_fix_loop
from aura.core.llm import LLM
from aura.core.pipeline import run_analysis

# =========================================================
# AURA CLI
# =========================================================

app = typer.Typer(help="AURA CLI", add_completion=False)


# ---------------------------------------------------------
# Basic utility commands
# ---------------------------------------------------------
@app.command()
def hello(
    name: str | None = typer.Option("world", "--name", "-n", help="Name to greet"),
) -> None:
    """Say hello (used by tests)."""
    typer.echo(f"Hello, {name}!")


@app.command("version")
def version_cmd() -> None:
    """Print CLI version in the format tests expect."""
    try:
        v = metadata.version("aura-audit")
    except metadata.PackageNotFoundError:
        v = "0.0.0-dev"
    typer.echo(f"AURA v{v}")


def _version_callback(value: bool | None) -> None:
    if value:
        try:
            v = metadata.version("aura-audit")
        except metadata.PackageNotFoundError:
            v = "0.0.0-dev"
        # tests that call `-m aura.cli --version` expect just the raw version
        typer.echo(v)
        raise typer.Exit()


@app.callback()
def _root(
    version: bool | None = typer.Option(
        None,
        "--version",
        "-V",
        help="Show version and exit",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    # no-op root; options handled via callback
    return


# ---------------------------------------------------------
# Core analyzer command
# ---------------------------------------------------------
@app.command("analyze")
def analyze(
    target: str,
    project: str = typer.Option(
        "default",
        "--project",
        "-p",
        help="Project name used for persistence",
    ),
    json_out: bool = typer.Option(
        False,
        "--json",
        help="Output full JSON result instead of a short summary",
    ),
) -> None:
    """Run analyzers and print a tiny summary or JSON."""
    res = run_analysis(target, project_name=project)

    if json_out:
        # Full machine-readable output
        typer.echo(json.dumps(res, indent=2, default=str))
    else:
        # Backwards-compatible summary (tests expect this style)
        findings = res.get("findings", [])
        score = res.get("score", 0)
        typer.echo(f"Findings: {len(findings)} | Score: {score}")


# ---------------------------------------------------------
# WEEK 4: Evaluation command
# ---------------------------------------------------------

# Module-level constants to avoid Ruff B008 (function calls in defaults)
DEFAULT_GOLDEN = Path("reports/golden/summary.sarif")
DEFAULT_REPORT = Path("reports/summary.sarif")
DEFAULT_OUT = Path("reports/metrics.json")


@app.command("eval")
def eval_cmd(
    golden: Annotated[
        Path,
        typer.Option("--golden", help="Golden SARIF file (baseline)"),
    ] = DEFAULT_GOLDEN,
    report: Annotated[
        Path,
        typer.Option("--report", help="Analyzer SARIF file to compare"),
    ] = DEFAULT_REPORT,
    out: Annotated[
        Path,
        typer.Option("--out", help="Where to save evaluation metrics"),
    ] = DEFAULT_OUT,
) -> None:
    """Compare analyzer report vs golden baseline and compute precision, recall, F1."""

    # Auto-create golden if missing
    if not golden.exists():
        typer.echo(f"[info] Golden not found at {golden}. Creating from {report}...")
        golden.parent.mkdir(parents=True, exist_ok=True)
        golden.write_text(report.read_text())

    # Run evaluation
    metrics = evaluate(report, golden)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(metrics, indent=2))

    # Append evaluation summary to index.md (ignored in git)
    idx = Path("reports/index.md")
    idx.parent.mkdir(parents=True, exist_ok=True)
    line = (
        f"\n### Evaluation\n"
        f"TP={metrics['tp']} FP={metrics['fp']} FN={metrics['fn']} • "
        f"P={metrics['precision']} R={metrics['recall']} F1={metrics['f1']}\n"
    )
    by_rule = metrics.get("by_rule", {})
    if by_rule:
        rules = sorted(by_rule.keys())
        line += "\n| Rule | TP | FP | FN | P | R | F1 |\n|---|---:|---:|---:|---:|---:|---:|\n"
        for r in rules:
            m = by_rule[r]
            line += (
                f"| `{r}` | {m['tp']} | {m['fp']} | {m['fn']} | "
                f"{m['precision']:.4f} | {m['recall']:.4f} | {m['f1']:.4f} |\n"
            )
    prefix = idx.read_text() if idx.exists() else "# AURA Report\n"
    idx.write_text(prefix + line)

    typer.echo(f"Wrote metrics → {out}")
    typer.echo(" ".join([f"{k}={v}" for k, v in metrics.items()]))


# ---------------------------------------------------------
# WEEK 5: Benchmarking command
# ---------------------------------------------------------


@app.command("benchmark")
def benchmark_cmd(
    target: Annotated[
        Path,
        typer.Option(
            "--target",
            "-t",
            help="Target contract file or directory to analyze",
        ),
    ] = Path("samples/contracts"),
    project: Annotated[
        str,
        typer.Option(
            "--project",
            "-p",
            help="Project name used for persistence",
        ),
    ] = "benchmark",
    runs: Annotated[
        int,
        typer.Option(
            "--runs",
            "-n",
            min=1,
            help="Number of times to run the analysis for timing",
        ),
    ] = 1,
    out: Annotated[
        Path,
        typer.Option(
            "--out",
            help="Where to save benchmark metrics JSON",
        ),
    ] = Path("reports/benchmark.json"),
) -> None:
    """Run analysis multiple times and record timing / basic stats."""

    durations: list[float] = []
    last_result: dict[str, object] | None = None

    for _ in range(runs):
        start = time.perf_counter()
        res = run_analysis(str(target), project_name=project)
        end = time.perf_counter()
        durations.append(end - start)
        last_result = res

    avg = sum(durations) / len(durations) if durations else 0.0
    payload: dict[str, object] = {
        "target": str(target),
        "project": project,
        "runs": runs,
        "durations_sec": durations,
        "avg_duration_sec": avg,
    }
    if isinstance(last_result, dict):
        findings = last_result.get("findings", [])
        n_findings = last_result.get("n_findings")
        if isinstance(n_findings, int):
            payload["n_findings_last_run"] = n_findings
        elif isinstance(findings, list):
            payload["n_findings_last_run"] = len(findings)
        payload["score_last_run"] = last_result.get("score")

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2))

    # Append a short section to reports/index.md
    idx = Path("reports/index.md")
    prefix = idx.read_text() if idx.exists() else "# AURA Report\n"
    idx.write_text(
        prefix
        + "\n### Benchmark\n"
        + f"- Target: `{target}`\n"
        + f"- Runs: {runs}\n"
        + f"- Avg duration: {avg:.4f} s\n"
    )

    typer.echo(f"Wrote benchmark → {out}")
    typer.echo(f"avg={avg:.4f}s over {runs} run(s)")


# ---------------------------------------------------------
# WEEK 6: Explain command (natural-language summary)
# ---------------------------------------------------------


@app.command("explain")
def explain_cmd(
    target: str,
    project: str = typer.Option(
        "default",
        "--project",
        "-p",
        help="Project name used for persistence",
    ),
    max_items: int = typer.Option(
        3,
        "--max-items",
        "-n",
        min=1,
        help="How many top issues to include in the explanation",
    ),
    output_format: str = typer.Option(
        "text",
        "--format",
        "-f",
        help="Output format: 'text' (default) or 'json'.",
    ),
    use_llm: bool = typer.Option(
        False,
        "--llm",
        help="Use the LLM to generate a natural-language explanation of the top findings.",
    ),
    include_fixes: bool = typer.Option(
        False,
        "--fixes",
        help="Include concrete remediation suggestions for each issue (only used with --llm).",
    ),
) -> None:
    """
    Run analysis and explain the most important findings.

    - Default: human-readable summary (static, no LLM).
    - --format json: machine-readable findings payload.
    - --llm: call the LLM to generate a natural-language explanation.
    - --llm --fixes: explanation + concrete remediation suggestions.
    """
    res = run_analysis(target, project_name=project)
    findings = res.get("findings", [])

    # If JSON requested, ignore LLM for now (LLM is text-only output).
    if output_format.lower() == "json":
        payload = {
            "target": target,
            "project": project,
            "total_issues": len(findings),
            "max_items": max_items,
            "findings": findings[:max_items],
        }
        typer.echo(json.dumps(payload, indent=2))
        return

    # LLM path: build appropriate prompt from findings and ask the LLM.
    if use_llm:
        if include_fixes:
            prompt = build_llm_remediation_prompt(findings, max_items=max_items)
        else:
            prompt = build_llm_explanation_prompt(findings, max_items=max_items)

        llm = LLM()
        explanation = llm.complete(prompt)
        typer.echo(explanation)
        return

    # Default text-only summary (existing behaviour used by tests).
    summary = summarize_findings(findings, max_items=max_items)
    typer.echo(summary)


@app.command("explain-llm")
def explain_llm_cmd(
    target: str,
    project: str = typer.Option(
        "default",
        "--project",
        "-p",
        help="Project name used for persistence",
    ),
    max_items: int = typer.Option(
        3,
        "--max-items",
        "-n",
        min=1,
        help="How many top issues to include in the LLM output",
    ),
    fixes: bool = typer.Option(
        False,
        "--fixes",
        help="Include concrete remediation steps and a diff-style patch for each top issue",
    ),
) -> None:
    """
    Run analysis and ask the LLM to produce a natural-language explanation
    of the most important findings.

    Use --fixes to request remediation steps + a patch-style diff.
    """
    res = run_analysis(target, project_name=project)
    findings = res.get("findings", [])

    if fixes:
        prompt = build_llm_remediation_prompt(findings, max_items=max_items)
    else:
        prompt = build_llm_explanation_prompt(findings, max_items=max_items)

    llm = LLM()
    explanation = llm.complete(prompt)
    typer.echo(explanation)


@app.command("llm")
def llm_cmd(
    prompt: str = typer.Argument(..., help="Prompt to send to the LLM"),
) -> None:
    """
    Send a quick prompt to the configured LLM and print the response.

    This is mainly a debug / smoke-test command for Week 7.
    """
    llm = LLM()
    reply = llm.complete(prompt)
    typer.echo(reply)


# ---------------------------------------------------------
# WEEK 10: PR-ready auto-fix command
# ---------------------------------------------------------


@app.command("fix")
def fix_cmd(
    target: str,
    rule: str = typer.Option(
        "",
        "--rule",
        help="Rule ID to fix (run once without --rule to list available rules).",
    ),
    project: str = typer.Option(
        "default",
        "--project",
        "-p",
        help="Project name used for persistence",
    ),
    max_items: int = typer.Option(
        10,
        "--max-items",
        "-n",
        min=1,
        help="How many findings to scan when listing rules.",
    ),
    write: bool = typer.Option(
        False,
        "--write",
        help="Apply the fix to the target file. Only writes when the verdict is VERIFIED.",
    ),
    max_retries: int = typer.Option(
        3,
        "--max-retries",
        min=1,
        help="Maximum verification attempts before giving up.",
    ),
    json_out: bool = typer.Option(
        False,
        "--json",
        help="Output the verification result as JSON instead of text.",
    ),
) -> None:
    """
    Generate and verify a PR-ready remediation diff for ONE specific finding rule.

    The diff is applied in an isolated workspace, compiled, and re-analyzed
    before being presented — a VERIFIED verdict means the target finding is
    confirmed gone with no new findings introduced.

    Usage:
    - List rules:
        aura fix <target>
    - Fix + verify one rule:
        aura fix <target> --rule <rule_id>
    - Fix, verify, and apply to the file:
        aura fix <target> --rule <rule_id> --write
    """
    if not Path(target).is_file():
        typer.echo(
            f"Error: '{target}' is not a file. `aura fix` only supports a single "
            "Solidity file target (see docs/PROJECT_BRIEF.md 'v1 does NOT')."
        )
        raise typer.Exit(code=1)

    res = run_analysis(target, project_name=project)
    findings = res.get("findings", [])

    if not findings:
        typer.echo("No issues detected. Nothing to fix.")
        return

    if not rule:
        seen = set()
        rules = []
        for f in findings:
            rid = str(f.get("rule_id") or f.get("category") or "").strip()
            if rid and rid not in seen:
                seen.add(rid)
                rules.append(rid)
            if len(rules) >= max_items:
                break

        typer.echo("Available rules for this target:")
        for r in rules:
            typer.echo(f"- {r}")
        typer.echo("\nRe-run with: aura fix <target> --rule <rule_id>")
        return

    match = None
    for f in findings:
        if str(f.get("rule_id") or "").strip() == rule:
            match = f
            break

    if match is None:
        typer.echo(f"No finding found for rule='{rule}'.")
        return

    llm = LLM()
    result = verify_fix_loop(target, match, rule, llm=llm, max_retries=max_retries)

    if json_out:
        payload = {
            "verdict": result.verdict,
            "attempts": result.attempts,
            "detail": result.detail,
            "degraded_reason": result.degraded_reason,
            "new_findings": result.new_findings,
            "diff": result.diff,
        }
        typer.echo(json.dumps(payload, indent=2))
    else:
        typer.echo(f"Verdict: {result.verdict} (attempt {result.attempts}/{max_retries})")
        typer.echo(result.detail)
        if result.new_findings:
            typer.echo("\nNew findings introduced:")
            for nf in result.new_findings:
                rid = nf.get("rule_id", "unknown-rule")
                sev = str(nf.get("severity", "UNKNOWN")).upper()
                typer.echo(f"- [{sev}] {rid}")
        typer.echo("")
        typer.echo(result.diff)

    if write:
        if result.verdict == "VERIFIED" and result.patched_source is not None:
            Path(target).write_text(result.patched_source, encoding="utf-8")
            typer.echo(f"\nWrote verified fix to {target}")
        else:
            typer.echo(f"\nRefusing to write: verdict is {result.verdict}, not VERIFIED.")

    if result.verdict in ("FAILED", "REGRESSED"):
        raise typer.Exit(code=1)


# ---------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------
if __name__ == "__main__":
    app()
