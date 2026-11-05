import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "ci" / "esegui-test.sh"


def test_script_exists():
    assert SCRIPT.is_file()


def test_script_delegates_to_run_checks_with_args():
    content = SCRIPT.read_text()
    assert 'exec bash scripts/run-checks.sh "$@"' in content


def test_invalid_argument_exits_non_zero():
    r = subprocess.run(
        ["bash", str(SCRIPT), "--boh"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert r.returncode != 0
