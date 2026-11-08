"""Tests for scripts/stato-epic2.sh (state of the «Epic 2 go-live chiuso» criteria, counted from the logs).

Contract between the script and these tests:
  - run as `bash scripts/stato-epic2.sh [DIR]`; DIR defaults to $PIENOGIUSTO_STATO
    (default ~/.local/state/azienda/pienogiusto);
  - STATO_EPIC2_OGGI=YYYY-MM-DD is the reference "today" (default: the real date); the window is the 7 days
    ending today (included);
  - DIR layout (fake copies in tests/fixtures/log-finti/):
      residui/pubblica.log.YYYYMMDD-HHMMSS-PID   one log per run of pubblica.sh
      verifica-url.log                           lines `YYYY-MM-DD OK|KO` (public-URL check, card #6)
      watchdog.log                               lines `YYYY-MM-DD attivo`
  - criterion 1: every day of the window has a run log with "gh-pages pubblicato" or "gia' online" and
    without "ERRORE"; criterion 2: every day of the window has an `OK` line (7 out of 7), no `KO`;
    criterion 3: the last watchdog.log line is `attivo` and dated today or yesterday;
  - stdout: one line per criterion, `criterio N: OK ...` or `criterio N: NO ...`;
  - exit 0 only if all 3 are OK, else 1.
"""
import os
import re
import shutil
import subprocess
from pathlib import Path

RADICE = Path(__file__).parents[2]
SCRIPT = RADICE / "scripts" / "stato-epic2.sh"
ROADMAP = RADICE / "docs" / "3_roadmap_macro.md"
FIXTURES = RADICE / "tests" / "fixtures" / "log-finti"
OGGI = "2026-11-01"


def lancia(cartella: Path):
    env = {**os.environ, "STATO_EPIC2_OGGI": OGGI}
    return subprocess.run(["bash", str(SCRIPT), str(cartella)], env=env, capture_output=True, text=True, timeout=30)


def esiti(r) -> dict:
    return {int(m.group(1)): m.group(2) for m in re.finditer(r"^criterio (\d): (OK|NO)", r.stdout, re.M)}


def copia_verde(tmp_path: Path) -> Path:
    dest = tmp_path / "stato"
    shutil.copytree(FIXTURES / "verde", dest)
    return dest


# ---- criterio 1: la roadmap riporta i 3 criteri di «chiuso» ------------------------------------------------

def sezione_epic2() -> str:
    righe = ROADMAP.read_text().splitlines()
    inizio = next(i for i, r in enumerate(righe) if "Epic 2" in r)
    fine = next((j for j in range(inizio + 1, len(righe)) if re.match(r"\s*- \[.\] Epic \d", righe[j])), len(righe))
    return "\n".join(righe[inizio:fine]).lower()


def test_roadmap_riporta_i_tre_criteri_di_chiuso():
    testo = sezione_epic2()
    assert "chiuso" in testo
    assert "7 giorni consecutivi" in testo and "senza interventi a mano" in testo   # criterio A
    assert "7 volte su 7" in testo and "#6" in testo                                # criterio B
    assert "watchdog" in testo                                                      # criterio C
    assert "stato-epic2.sh" in testo                                                # how to count them


# ---- criterio 2: lo script conta i 3 criteri e mostra lo stato di ciascuno ---------------------------------

def test_script_mostra_lo_stato_di_ciascun_criterio(tmp_path):
    r = lancia(copia_verde(tmp_path))
    assert esiti(r) == {1: "OK", 2: "OK", 3: "OK"}, r.stdout + r.stderr


def test_script_conta_i_giorni_e_le_verifiche(tmp_path):
    r = lancia(copia_verde(tmp_path))
    assert re.search(r"criterio 1: OK.*7\s*/\s*7", r.stdout)
    assert re.search(r"criterio 2: OK.*7\s*/\s*7", r.stdout)


def test_giorno_senza_pubblicazione_rompe_solo_il_criterio_1(tmp_path):
    stato = copia_verde(tmp_path)
    (stato / "residui" / "pubblica.log.20261029-091500-104").rename(stato / "residui" / "altro.txt")
    r = lancia(stato)
    assert esiti(r) == {1: "NO", 2: "OK", 3: "OK"}, r.stdout
    assert re.search(r"criterio 1: NO.*6\s*/\s*7", r.stdout)
    assert r.returncode == 1


def test_giorno_con_errore_non_conta_come_pubblicato(tmp_path):
    stato = copia_verde(tmp_path)
    log = stato / "residui" / "pubblica.log.20261028-091500-103"
    log.write_text("== test\n== build\nERRORE: fallito al passo build (exit 1)\n")
    r = lancia(stato)
    assert esiti(r)[1] == "NO", r.stdout
    assert r.returncode == 1


def test_verifica_url_ko_rompe_solo_il_criterio_2(tmp_path):
    stato = copia_verde(tmp_path)
    v = stato / "verifica-url.log"
    v.write_text(v.read_text().replace("2026-10-30 OK", "2026-10-30 KO"))
    r = lancia(stato)
    assert esiti(r) == {1: "OK", 2: "NO", 3: "OK"}, r.stdout
    assert re.search(r"criterio 2: NO.*6\s*/\s*7", r.stdout)
    assert r.returncode == 1


def test_watchdog_assente_o_vecchio_rompe_solo_il_criterio_3(tmp_path):
    stato = copia_verde(tmp_path)
    (stato / "watchdog.log").write_text("2026-10-20 attivo\n")
    r = lancia(stato)
    assert esiti(r) == {1: "OK", 2: "OK", 3: "NO"}, r.stdout
    (stato / "watchdog.log").rename(stato / "watchdog.log.spostato")
    r = lancia(stato)
    assert esiti(r) == {1: "OK", 2: "OK", 3: "NO"}, r.stdout
    assert r.returncode == 1


# ---- criterio 3: passa con i log che soddisfano i criteri, fallisce con quelli che non li soddisfano -------

def test_fixture_verde_esce_con_0():
    r = lancia(FIXTURES / "verde")
    assert r.returncode == 0, r.stdout + r.stderr


def test_fixture_rosso_esce_con_1_e_mostra_tutti_e_tre_i_criteri():
    r = lancia(FIXTURES / "rosso")
    assert r.returncode == 1
    assert esiti(r) == {1: "NO", 2: "NO", 3: "NO"}, r.stdout + r.stderr
