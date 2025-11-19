from __future__ import annotations

import json
import time
from importlib import metadata
from pathlib import Path
from typing import Annotated

import typer

from aura.core.evaluation import evaluate
from aura.core.explain import build_llm_explanation_prompt, summarize_findings
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
        v = metadata.version("aura")
    except metadata.PackageNotFoundError:
        v = "0.0.0-dev"
    typer.echo(f"AURA v{v}")


def _version_callback(value: bool | None) -> None:
    if value:
        try:
            v = metadata.version("aura")
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
) -> None:
    """
    Run analysis and print a simple natural-language explanation
    of the most important findings.
    """
    res = run_analysis(target, project_name=project)
    findings = res.get("findings", [])
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
        help="How many top issues to include in the LLM explanation",
    ),
) -> None:
    """
    Run analysis and ask the LLM to produce a natural-language explanation
    of the most important findings.

    Uses a stubbed LLM if no real API key is configured.
    """
    res = run_analysis(target, project_name=project)
    findings = res.get("findings", [])

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
# Entrypoint
# ---------------------------------------------------------
if __name__ == "__main__":
    app()
