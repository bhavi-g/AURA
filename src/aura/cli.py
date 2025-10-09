import typer
from rich import print as rprint

from . import __version__

app = typer.Typer(add_completion=False, help="AURA — AI Unified Risk Auditor")


@app.command()
def version():
    """Show AURA version."""
    rprint(f"[bold cyan]AURA[/] v{__version__}")


@app.command()
def hello(
    name: str | None = typer.Option(None, "--name", "-n", help="Your name"),
):
    """Sanity check command."""
    who = name or "world"
    rprint(f":sparkles: Hello, {who}! AURA is ready.")


def main():
    """Console entrypoint."""
    app()


if __name__ == "__main__":
    main()
