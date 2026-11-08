"""Tests for the archive step of scripts/spinta.sh (PGD-7), with a fake `gh` and a file:// index.

Same setup as the historical spinta tests: the stub `gh` answers `run list` with $STUB_IN_CORSO and records
every call; the index is a local directory served through file://; "today" is injected.
"""
import gzip
import json
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[2] / "scripts" / "spinta.sh"
OGGI = "2026-10-08"
IERI = "2026-10-07T08:00:00+02:00"  # fresh data: spinta does not launch the workflow
L_ALTRO = "2026-10-06T08:00:00+02:00"  # stale data: spinta launches the workflow

STUB_GH = """#!/usr/bin/env bash
echo "$*" >> "$STUB_CHIAMATE"
case "$1 $2" in
  "run list") echo "${STUB_IN_CORSO:-0}" ;;
  "workflow run") exit 0 ;;
  *) echo "unexpected: $*" >&2; exit 2 ;;
esac
"""


@pytest.fixture
def ambiente(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(STUB_GH)
    gh.chmod(0o755)
    env = {
        "PATH": f"{bin_dir}:/usr/bin:/bin",
        "HOME": str(tmp_path),
        "STUB_CHIAMATE": str(tmp_path / "chiamate.txt"),
        "PIENOGIUSTO_SPINTA_LOG": str(tmp_path / "state" / "spinta.log"),
        "PIENOGIUSTO_SPINTA_STATO": str(tmp_path / "state" / "spinta.ultimo"),
        "PIENOGIUSTO_ARCHIVIO": str(tmp_path / "arch"),
        "PIENOGIUSTO_OGGI": OGGI,
    }
    return tmp_path, env


def pubblica_indice(tmp_path, prezzi_del):
    """A published site on disk: index.json + p/BA.json.gz. Returns the file:// URL of index.json."""
    sito = tmp_path / "sito"
    (sito / "p").mkdir(parents=True, exist_ok=True)
    (sito / "p" / "BA.json.gz").write_bytes(gzip.compress(json.dumps({"schema": 1, "impianti": []}).encode()))
    (sito / "index.json").write_text(json.dumps({
        "schema": 1, "prezziDel": prezzi_del, "comuni": "comuni.json.gz",
        "province": [{"sigla": "BA", "file": "p/BA.json.gz", "n": 1, "bbox": [0, 0, 0, 0]}]}))
    return f"file://{sito}/index.json"


def lancia(tmp_path, env, *args, **extra):
    # cwd is NOT the repo: the script must find its own python package
    return subprocess.run(["bash", str(SCRIPT), *args], env={**env, **extra}, capture_output=True, text=True,
                          timeout=60, cwd=tmp_path)


def lanci(tmp_path):
    f = tmp_path / "chiamate.txt"
    righe = f.read_text().splitlines() if f.exists() else []
    return [r for r in righe if r.startswith("workflow run")]


def righe_diario(tmp_path):
    return (tmp_path / "state" / "spinta.log").read_text().splitlines()


def test_archivia_a_ogni_giro_anche_quando_non_lancia(ambiente):
    tmp_path, env = ambiente
    r = lancia(tmp_path, env, PIENOGIUSTO_INDEX_URL=pubblica_indice(tmp_path, IERI))
    assert r.returncode == 0, r.stderr
    assert lanci(tmp_path) == []
    giorno = tmp_path / "arch" / "2026-10-07"
    assert (giorno / "index.json").is_file()
    assert (giorno / "p" / "BA.json.gz").is_file()


def test_archivia_anche_quando_lancia_il_workflow(ambiente):
    tmp_path, env = ambiente
    r = lancia(tmp_path, env, PIENOGIUSTO_INDEX_URL=pubblica_indice(tmp_path, L_ALTRO))
    assert r.returncode == 0, r.stderr
    assert len(lanci(tmp_path)) == 1
    assert (tmp_path / "arch" / "2026-10-06" / "index.json").is_file()
    assert len(righe_diario(tmp_path)) == 1


def test_archivio_predefinito_sotto_home(ambiente):
    tmp_path, env = ambiente
    env = {k: v for k, v in env.items() if k != "PIENOGIUSTO_ARCHIVIO"}
    r = lancia(tmp_path, env, PIENOGIUSTO_INDEX_URL=pubblica_indice(tmp_path, IERI))
    assert r.returncode == 0, r.stderr
    assert (tmp_path / ".local" / "state" / "pienogiusto" / "archivio" / "2026-10-07" / "index.json").is_file()


def test_secondo_giro_stesso_giorno_non_rompe_niente(ambiente):
    tmp_path, env = ambiente
    url = pubblica_indice(tmp_path, IERI)
    assert lancia(tmp_path, env, PIENOGIUSTO_INDEX_URL=url).returncode == 0
    assert lancia(tmp_path, env, PIENOGIUSTO_INDEX_URL=url).returncode == 0
    assert [p.name for p in (tmp_path / "arch").iterdir()] == ["2026-10-07"]
    assert len(righe_diario(tmp_path)) == 2  # one line per round


def _archivio_guasto(tmp_path):
    """<state>/arch is a regular file: the archive directory cannot be created."""
    stato = tmp_path / "stato-archivio"
    stato.mkdir()
    (stato / "arch").write_text("sono un file, non una cartella")
    return stato, stato / "arch"


def test_archivio_guasto_stesso_codice_di_uscita_errore_nel_log_e_una_riga_in_spinta_log(ambiente):
    tmp_path, env = ambiente
    stato, archivio = _archivio_guasto(tmp_path)
    r = lancia(tmp_path, env, PIENOGIUSTO_INDEX_URL=pubblica_indice(tmp_path, L_ALTRO),
               PIENOGIUSTO_ARCHIVIO=str(archivio))
    assert r.returncode == 0, r.stderr  # same exit code as without the archive step
    assert len(lanci(tmp_path)) == 1  # the push still happens
    assert (stato / "archivio.log").read_text().strip(), "archive error must be saved in archivio.log"
    (riga,) = righe_diario(tmp_path)  # spinta.log stays one line per round
    assert "azione=lanciato" in riga


def test_archivio_guasto_con_indice_irraggiungibile_esce_ancora_1(ambiente):
    tmp_path, env = ambiente
    _, archivio = _archivio_guasto(tmp_path)
    r = lancia(tmp_path, env, PIENOGIUSTO_INDEX_URL=f"file://{tmp_path}/non-esiste.json",
               PIENOGIUSTO_ARCHIVIO=str(archivio))
    assert r.returncode == 1
    assert lanci(tmp_path) == []


def test_prova_non_crea_nessun_file(ambiente):
    tmp_path, env = ambiente
    r = lancia(tmp_path, env, "--prova", PIENOGIUSTO_INDEX_URL=pubblica_indice(tmp_path, L_ALTRO))
    assert r.returncode == 0, r.stderr
    assert not (tmp_path / "arch").exists()
    assert not (tmp_path / "archivio.log").exists()
    assert not (tmp_path / "state").exists()
    assert not (tmp_path / ".local").exists()
