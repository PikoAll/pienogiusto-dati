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


def test_mappa_no_longer_lists_removed_files_as_active():
    """docs/mappa.md must not describe the set-aside files as live files."""
    text = (ROOT / "docs/mappa.md").read_text(encoding="utf-8")
    removed = [
        "scripts/spinta.sh",
        "scripts/watchdog.sh",
        "tests/integration/test_spinta.py",
        "tests/integration/test_watchdog.py",
    ] + ["scripts/systemd/" + unit for unit in SYSTEMD_UNITS]
    still_listed = [p for p in removed if f"`{p}`" in text]
    assert not still_listed, f"mappa.md still lists: {still_listed}"


def _d10_section():
    text = (ROOT / "docs/DECISIONI.md").read_text(encoding="utf-8")
    start = text.index("### D10")
    end = text.index("\n### ", start + 1)
    return text[start:end]


def test_architecture_doc_and_readme_show_the_new_flow():
    arch = (ROOT / "docs/2_architettura_stack.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for name, text in (("docs/2_architettura_stack.md", arch), ("README.md", readme)):
        assert "gh-pages" in text, f"{name} must describe the gh-pages flow"
        assert "artefatto" not in text, f"{name} still shows the old artifact flow"
    assert "Actions -> artefatto" not in arch


def test_decision_d10_is_marked_superseded_with_original_text_intact():
    section = _d10_section()
    assert section.startswith("### D10 · Keepalive tolto, watchdog al suo posto")
    assert "sostituita da D13" in section
    assert "watchdog" in section.lower()


def test_decisioni_lists_manual_steps_for_giuseppe():
    text = (ROOT / "docs/DECISIONI.md").read_text(encoding="utf-8")
    assert (
        "systemctl --user disable --now pienogiusto-dati-spinta.timer "
        "pienogiusto-watchdog.timer"
    ) in text
    assert (
        "gh api -X PUT repos/PikoAll/pienogiusto-dati/actions/workflows/pubblica.yml/disable"
    ) in text
    assert ".github/workflows/pubblica.yml" in text
    assert "MANUAL" in text.upper()


def test_no_live_references_to_removed_scripts():
    """Card grep: spinta.sh / watchdog.sh outside *.backup and DECISIONI history."""
    skip_files = {
        ROOT / "docs/DECISIONI.md",
        Path(__file__).resolve(),  # this test names the files on purpose
    }
    live = []
    for pattern in ("*.md", "*.py", "*.sh"):
        for path in ROOT.rglob(pattern):
            rel = path.relative_to(ROOT)
            if path in skip_files or ".git" in rel.parts:
                continue
            if any(part.endswith(".backup") for part in rel.parts):
                continue
            if any(part.startswith(".venv") or part == "venv" for part in rel.parts):
                continue
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if "spinta.sh" in line or "watchdog.sh" in line:
                    live.append(f"{rel}:{n}")
    assert not live, f"live references left: {live}"


def test_pi_node_script_no_longer_ignores_removed_tests():
    text = (ROOT / "scripts/nodo-pi/pubblica.sh").read_text(encoding="utf-8")
    assert "test_spinta" not in text
    assert "test_watchdog" not in text
    assert "-m pytest -q" in text  # the test step itself must remain
