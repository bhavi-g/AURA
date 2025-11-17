import json
from importlib import metadata

import typer

from aura.core.pipeline import run_analysis

app = typer.Typer(help="AURA CLI (alt entry)", add_completion=False)


@app.command()
def hello(name: str | None = typer.Option("world", "--name", "-n", help="Name to greet")) -> None:
    """Say hello."""
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
    return


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
        typer.echo(json.dumps(res, indent=2, default=str))
    else:
        findings = res.get("findings", [])
        score = res.get("score", 0)
        typer.echo(f"Findings: {len(findings)} | Score: {score}")


if __name__ == "__main__":
    app()
