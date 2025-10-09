import re
import shutil
import subprocess
import sys


def run(args):
    return subprocess.run(args, capture_output=True, text=True)


def test_package_import_and_version():
    import aura  # noqa: PLC0415 (import inside test)

    assert isinstance(aura.__version__, str) and aura.__version__, "empty __version__?!"
    assert re.match(r"^\d+\.\d+\.\d+", aura.__version__)


def test_module_cli_hello_and_version():
    out = run([sys.executable, "-m", "aura.cli", "hello", "--name", "Test"]).stdout
    assert "Hello, Test" in out
    out = run([sys.executable, "-m", "aura.cli", "version"]).stdout
    assert "AURA v" in out


def test_console_script_exists_and_works():
    exe = shutil.which("aura")
    assert exe, "console script 'aura' not found on PATH (is venv active and package reinstalled?)"
    out = run([exe, "version"]).stdout
    assert "AURA v" in out
