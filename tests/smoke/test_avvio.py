"""Smoke test: the real entrypoint (`python -m pienogiusto_dati.pubblica`) starts as a process."""
import subprocess
import sys
from pathlib import Path

RADICE = Path(__file__).parents[2]
FIXTURES = RADICE / "tests" / "fixtures"


def avvia(*argomenti):
    return subprocess.run([sys.executable, "-m", "pienogiusto_dati.pubblica", *argomenti],
                          cwd=RADICE, capture_output=True, text=True, timeout=60)


def test_help():
    r = avvia("--help")
    assert r.returncode == 0 and "--indice-precedente" in r.stdout


def test_processo_vero_fail_closed(tmp_path):
    # real thresholds: the ~160-station fixture must be refused, nothing written
    r = avvia("--anagrafica", str(FIXTURES / "anagrafica_reale.csv"),
              "--prezzi", str(FIXTURES / "prezzi_reale.csv"), "--uscita", str(tmp_path / "site"))
    assert r.returncode == 1
    assert "CANCELLO FALLITO" in r.stderr and "impianti" in r.stderr
    assert list(tmp_path.iterdir()) == []
