import subprocess
import sys


def run_cli(args):
    return subprocess.run(
        [sys.executable, "-m", "aura.cli", *args],
        capture_output=True,
        text=True,
    )


def test_hello():
    out = run_cli(["hello", "--name", "AURA"]).stdout
    assert "Hello, AURA" in out


def test_version():
    out = run_cli(["version"]).stdout
    assert "AURA v" in out
