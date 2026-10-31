"""Tests for scripts/spinta.sh, with a fake `gh` first in PATH and a file:// index.

The stub answers `gh run list` with $STUB_IN_CORSO (number of running/queued runs) and records every
invocation in $STUB_CHIAMATE. The index is a local file, the "today" date is injected.
"""
import json
import os
import subprocess
import time
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[2] / "scripts" / "spinta.sh"
OGGI = "2026-10-08"

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
        "PIENOGIUSTO_OGGI": OGGI,
    }
    return tmp_path, env


def index(tmp_path, prezzi_del):
    f = tmp_path / "index.json"
    f.write_text(json.dumps({"schema": 1, "prezziDel": prezzi_del}))
    return f"file://{f}"


def lancia(env, *args, **extra):
    return subprocess.run(["bash", str(SCRIPT), *args], env={**env, **extra}, capture_output=True, text=True,
                          timeout=30)


def lanci(tmp_path):
    f = tmp_path / "chiamate.txt"
    righe = f.read_text().splitlines() if f.exists() else []
    return [r for r in righe if r.startswith("workflow run")]


def diario(tmp_path):
    return (tmp_path / "state" / "spinta.log").read_text().splitlines()


def test_dato_di_ieri_non_lancia(ambiente):
    tmp_path, env = ambiente
    r = lancia(env, PIENOGIUSTO_INDEX_URL=index(tmp_path, "2026-10-07T08:00:00+02:00"))
    assert r.returncode == 0, r.stderr
    assert lanci(tmp_path) == []
    (riga,) = diario(tmp_path)
    assert "prezziDel=2026-10-07" in riga and "azione=nessuna" in riga


def test_dato_di_ieri_l_altro_lancia(ambiente):
    tmp_path, env = ambiente
    r = lancia(env, PIENOGIUSTO_INDEX_URL=index(tmp_path, "2026-10-06T08:00:00+02:00"))
    assert r.returncode == 0, r.stderr
    assert lanci(tmp_path) == ["workflow run pubblica.yml -R PikoAll/pienogiusto-dati"]
    (riga,) = diario(tmp_path)
    assert "prezziDel=2026-10-06" in riga and "azione=lanciato" in riga
    assert (tmp_path / "state" / "spinta.ultimo").exists()


def test_dato_molto_vecchio_lancia(ambiente):
    tmp_path, env = ambiente
    lancia(env, PIENOGIUSTO_INDEX_URL=index(tmp_path, "2026-09-30T08:00:00+02:00"))
    assert len(lanci(tmp_path)) == 1


def test_giro_gia_in_corso_non_lancia(ambiente):
    tmp_path, env = ambiente
    r = lancia(env, PIENOGIUSTO_INDEX_URL=index(tmp_path, "2026-10-06T08:00:00+02:00"), STUB_IN_CORSO="1")
    assert r.returncode == 0, r.stderr
    assert lanci(tmp_path) == []
    assert "azione=giro-in-corso" in diario(tmp_path)[0]


def test_lancio_meno_di_due_ore_fa_non_rilancia(ambiente):
    tmp_path, env = ambiente
    (tmp_path / "state").mkdir()
    (tmp_path / "state" / "spinta.ultimo").write_text(str(int(time.time()) - 3600))
    lancia(env, PIENOGIUSTO_INDEX_URL=index(tmp_path, "2026-10-06T08:00:00+02:00"))
    assert lanci(tmp_path) == []
    assert "azione=lancio-recente" in diario(tmp_path)[0]


def test_lancio_piu_di_due_ore_fa_rilancia(ambiente):
    tmp_path, env = ambiente
    (tmp_path / "state").mkdir()
    (tmp_path / "state" / "spinta.ultimo").write_text(str(int(time.time()) - 2 * 3600 - 60))
    lancia(env, PIENOGIUSTO_INDEX_URL=index(tmp_path, "2026-10-06T08:00:00+02:00"))
    assert len(lanci(tmp_path)) == 1


def test_prova_stampa_senza_lanciare_ne_scrivere(ambiente):
    tmp_path, env = ambiente
    r = lancia(env, "--prova", PIENOGIUSTO_INDEX_URL=index(tmp_path, "2026-10-06T08:00:00+02:00"))
    assert r.returncode == 0, r.stderr
    assert "lancerei" in r.stdout and "prezziDel=2026-10-06" in r.stdout
    assert lanci(tmp_path) == []
    assert not (tmp_path / "state").exists()


def test_prova_dato_fresco_dice_che_non_fa_nulla(ambiente):
    tmp_path, env = ambiente
    r = lancia(env, "--prova", PIENOGIUSTO_INDEX_URL=index(tmp_path, "2026-10-07T08:00:00+02:00"))
    assert r.returncode == 0, r.stderr
    assert "non lancio" in r.stdout and "nessuna" in r.stdout


def test_indice_irraggiungibile_e_errore_senza_lancio(ambiente):
    tmp_path, env = ambiente
    r = lancia(env, PIENOGIUSTO_INDEX_URL=f"file://{tmp_path}/non-esiste.json")
    assert r.returncode == 1
    assert lanci(tmp_path) == []
    assert "ERRORE" in diario(tmp_path)[0]


def test_indice_senza_prezzi_del_e_errore(ambiente):
    tmp_path, env = ambiente
    f = tmp_path / "index.json"
    f.write_text("{}")
    r = lancia(env, PIENOGIUSTO_INDEX_URL=f"file://{f}")
    assert r.returncode == 1
    assert lanci(tmp_path) == []


def test_argomento_sconosciuto_esce_2(ambiente):
    tmp_path, env = ambiente
    r = lancia(env, "--boh")
    assert r.returncode == 2
