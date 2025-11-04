import json
from importlib import metadata
from pathlib import Path
from typing import Annotated

import typer

from aura.core.evaluation import evaluate
from aura.core.pipeline import run_analysis

app = typer.Typer(help="AURA CLI", add_completion=False)


@app.command()
def hello(name: str | None = typer.Option("world", "--name", "-n", help="Name to greet")) -> None:
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
    )
) -> None:
    # no-op root; options handled via callback
    return


@app.command("analyze")
def analyze(
    target: str,
    project: str = typer.Option("default", "--project", "-p"),
) -> None:
    """Run analyzers and print a tiny summary."""
    res = run_analysis(target, project_name=project)
    findings = res.get("findings", [])
    score = res.get("score", 0)
    typer.echo(f"Findings: {len(findings)} | Score: {score}")


# ----------------------------------------------------------
# WEEK 4: Evaluation command
# ----------------------------------------------------------


# Module-level constants to avoid B008 (no function calls in defaults)
DEFAULT_GOLDEN = Path("reports/golden/summary.sarif")
DEFAULT_REPORT = Path("reports/summary.sarif")
DEFAULT_OUT = Path("reports/metrics.json")


@app.command("eval")
def eval_cmd(
    golden: Annotated[
        Path, typer.Option("--golden", help="Golden SARIF file (baseline)")
    ] = DEFAULT_GOLDEN,
    report: Annotated[
        Path, typer.Option("--report", help="Analyzer SARIF file to compare")
    ] = DEFAULT_REPORT,
    out: Annotated[
        Path, typer.Option("--out", help="Where to save evaluation metrics")
    ] = DEFAULT_OUT,
) -> None:
    """Compare analyzer report vs golden baseline and compute precision, recall, F1."""
    # Optional convenience: auto-create golden if missing
    if not golden.exists():
        typer.echo(f"[info] Golden not found at {golden}. Creating from {report}...")
        golden.parent.mkdir(parents=True, exist_ok=True)
        golden.write_text(report.read_text())

    metrics = evaluate(report, golden)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(metrics, indent=2))
    typer.echo(f"Wrote metrics → {out}")
    typer.echo(" ".join([f"{k}={v}" for k, v in metrics.items()]))


if __name__ == "__main__":
    app()
