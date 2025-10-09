import shutil
import subprocess


def have(cmd):
    return shutil.which(cmd) is not None


def run_ok(cmd):
    p = subprocess.run([cmd, "--version"], capture_output=True, text=True)
    return p.returncode == 0


def test_tool_black_installed():
    assert have("black") and run_ok("black")


def test_tool_ruff_installed():
    assert have("ruff") and run_ok("ruff")


def test_tool_pytest_installed():
    assert have("pytest") and run_ok("pytest")


def test_tool_precommit_installed():
    assert have("pre-commit") and run_ok("pre-commit")
