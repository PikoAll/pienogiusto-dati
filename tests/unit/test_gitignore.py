import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _check_ignore(path):
    return subprocess.run(
        ["git", "check-ignore", "--no-index", path],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )


def test_build_dir_is_ignored():
    r = _check_ignore("build/lib/pienogiusto_dati/x.py")
    assert r.returncode == 0
    assert r.stdout.strip() == "build/lib/pienogiusto_dati/x.py"


def test_file_with_build_in_name_not_ignored():
    assert _check_ignore("pienogiusto_dati/build_dati.py").returncode == 1


def test_flutter_entries_not_added():
    assert _check_ignore("local.properties").returncode == 1
