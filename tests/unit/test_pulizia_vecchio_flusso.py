"""Card #20: the old push/watchdog flow is set aside as .backup (never deleted)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

SYSTEMD_UNITS = [
    "pienogiusto-dati-spinta.service",
    "pienogiusto-dati-spinta.timer",
    "pienogiusto-watchdog.service",
    "pienogiusto-watchdog.timer",
]


def _set_aside(rel, marker):
    """The original is gone and the .backup copy still holds the old content."""
    assert not (ROOT / rel).exists(), f"{rel} must no longer be active"
    backup = ROOT / (rel + ".backup")
    assert backup.is_file(), f"{rel}.backup must exist (rename, not delete)"
    assert marker in backup.read_text(encoding="utf-8")


def test_spinta_sh_is_set_aside():
    _set_aside("scripts/spinta.sh", "gh")


def test_watchdog_sh_is_set_aside():
    _set_aside("scripts/watchdog.sh", "gh")


def test_systemd_dir_is_set_aside_with_all_units():
    assert not (ROOT / "scripts/systemd").exists()
    backup = ROOT / "scripts/systemd.backup"
    assert backup.is_dir()
    for unit in SYSTEMD_UNITS:
        assert (backup / unit).is_file(), unit


def test_old_flow_tests_are_set_aside():
    _set_aside("tests/integration/test_spinta.py", "def test_")
    _set_aside("tests/integration/test_watchdog.py", "def test_")


def test_pi_node_script_no_longer_ignores_removed_tests():
    text = (ROOT / "scripts/nodo-pi/pubblica.sh").read_text(encoding="utf-8")
    assert "test_spinta" not in text
    assert "test_watchdog" not in text
    assert "-m pytest -q" in text  # the test step itself must remain
