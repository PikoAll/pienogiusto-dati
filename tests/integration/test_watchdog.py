"""Tests for scripts/watchdog.sh, with a fake `gh` first in PATH.

The stub answers the state query with $STUB_STATO (or fails if $STUB_ERRORE is set)
and records every invocation in $STUB_CHIAMATE.
"""
import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[2] / "scripts" / "watchdog.sh"

STUB_GH = """#!/usr/bin/env bash
echo "$*" >> "$STUB_CHIAMATE"
if [ -n "${STUB_ERRORE:-}" ]; then echo "HTTP 401: Bad credentials" >&2; exit 1; fi
case "$1" in
  api) echo "$STUB_STATO" ;;
  workflow) exit 0 ;;
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
        "PIENOGIUSTO_WATCHDOG_LOG": str(tmp_path / "state" / "watchdog.log"),
    }
    return tmp_path, env


def lancia(env, **extra):
    return subprocess.run(["bash", str(SCRIPT)], env={**env, **extra}, capture_output=True, text=True, timeout=30)


def chiamate(tmp_path):
    f = tmp_path / "chiamate.txt"
    return f.read_text().splitlines() if f.exists() else []


def diario(tmp_path):
    return (tmp_path / "state" / "watchdog.log").read_text().splitlines()


def test_workflow_attivo_non_tocca_nulla(ambiente):
    tmp_path, env = ambiente
    r = lancia(env, STUB_STATO="active")
    assert r.returncode == 0, r.stderr
    assert chiamate(tmp_path) == ["api repos/PikoAll/pienogiusto-dati/actions/workflows/pubblica.yml --jq .state"]
    (riga,) = diario(tmp_path)
    assert "OK" in riga and "active" in riga


def test_workflow_disattivato_per_inattivita_riattiva_e_lancia(ambiente):
    tmp_path, env = ambiente
    r = lancia(env, STUB_STATO="disabled_inactivity")
    assert r.returncode == 0, r.stderr
    assert chiamate(tmp_path)[1:] == [
        "workflow enable pubblica.yml -R PikoAll/pienogiusto-dati",
        "workflow run pubblica.yml -R PikoAll/pienogiusto-dati",
    ]
    (riga,) = diario(tmp_path)
    assert "RIATTIVATO" in riga


def test_gh_in_errore_esce_rosso_e_scrive_il_diario(ambiente):
    tmp_path, env = ambiente
    r = lancia(env, STUB_ERRORE="1", STUB_STATO="active")
    assert r.returncode != 0
    (riga,) = diario(tmp_path)
    assert "ERRORE" in riga and "401" in riga


def test_disattivato_a_mano_non_viene_riattivato(ambiente):
    tmp_path, env = ambiente
    r = lancia(env, STUB_STATO="disabled_manually")
    assert r.returncode != 0
    assert len(chiamate(tmp_path)) == 1  # only the state query
    assert "disabled_manually" in diario(tmp_path)[0]


def test_idempotente_il_diario_si_allunga_e_basta(ambiente):
    tmp_path, env = ambiente
    lancia(env, STUB_STATO="active")
    lancia(env, STUB_STATO="active")
    assert len(diario(tmp_path)) == 2


def test_repo_configurabile(ambiente):
    tmp_path, env = ambiente
    lancia(env, STUB_STATO="active", PIENOGIUSTO_REPO="altro/repo")
    assert chiamate(tmp_path)[0].startswith("api repos/altro/repo/")
