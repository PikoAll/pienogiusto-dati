"""Tests for scripts/nodo-pi/pubblica.sh (publication from the home node) and its systemd --user units.

No network, no token, no real key. Contract between the script and these tests:
  - run as `bash scripts/nodo-pi/pubblica.sh` (the script moves to the repo root by itself);
  - PIENOGIUSTO_PYTHON      interpreter used for every python step (here: a stub that records the steps);
  - PIENOGIUSTO_STATO       state dir (default ~/.local/state/azienda/pienogiusto): `pubblica.log`,
                            `site/` (output dir of the build), `residui/`, `residui/vecchi/`;
  - PIENOGIUSTO_INDEX_URL   URL (here file://) of the online index.json, to compare `prezziDel`;
  - PUBBLICA=si|no          (default no) enables the git part; PUBBLICA_REMOTO = remote URL/path;
  - PIENOGIUSTO_ENV_FILE    env file with TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID;
  - steps, in order, named: test, build, contract, pubblicazione.
The stub python records "pytest ...", "build ..." (-m pienogiusto_dati.pubblica --uscita DIR ...) and
"contract ..." (-m pytest with PIENOGIUSTO_SITE set) in $STUB_CHIAMATE; a stub curl records Telegram calls.
"""
import os
import subprocess
import time
from pathlib import Path

import pytest

RADICE = Path(__file__).parents[2]
SCRIPT = RADICE / "scripts" / "nodo-pi" / "pubblica.sh"
SERVICE = RADICE / "scripts" / "nodo-pi" / "azienda-pienogiusto.service"
TIMER = RADICE / "scripts" / "nodo-pi" / "azienda-pienogiusto.timer"
DECISIONI = RADICE / "docs" / "DECISIONI.md"

PREZZI_DEL = "2026-10-29T08:00:00+01:00"

STUB_PYTHON = r"""#!/usr/bin/env bash
if [ "$1" = "-m" ] && [ "$2" = "pytest" ]; then
  if [ -n "$PIENOGIUSTO_SITE" ]; then passo=contract; else passo=pytest; fi
  echo "$passo $*" >> "$STUB_CHIAMATE"
  if [ "$STUB_FALLISCE" = "$passo" ]; then echo "stub: $passo fallito" >&2; exit 1; fi
  exit 0
fi
if [ "$1" = "-m" ] && [ "$2" = "pienogiusto_dati.pubblica" ]; then
  echo "build $*" >> "$STUB_CHIAMATE"
  if [ "$STUB_FALLISCE" = "build" ]; then echo "stub: build fallito" >&2; exit 1; fi
  uscita=""
  while [ $# -gt 0 ]; do
    if [ "$1" = "--uscita" ]; then uscita="$2"; fi
    shift
  done
  if [ "$STUB_NIENTE_SITE" = "1" ]; then echo "Niente di nuovo: non ripubblico."; exit 0; fi
  mkdir -p "$uscita/p"
  echo "{\"schema\":1,\"prezziDel\":\"$STUB_PREZZI_DEL\",\"province\":[],\"comuni\":\"comuni.json.gz\"}" > "$uscita/index.json"
  echo dati > "$uscita/p/MI.json.gz"
  echo "{}" > "$uscita/report.json"
  exit 0
fi
exec /usr/bin/python3 "$@"
"""

STUB_CURL = r"""#!/usr/bin/env bash
case "$*" in
  *api.telegram.org*) echo "$*" >> "$STUB_TELEGRAM"; echo '{"ok":true}'; exit 0 ;;
esac
exec /usr/bin/curl "$@"
"""


def git(cwd, *args, env=None):
    e = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
         "GIT_COMMITTER_EMAIL": "t@t", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"}
    r = subprocess.run(["git", *args], cwd=cwd, env=e, capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def scrivi_eseguibile(percorso: Path, testo: str):
    percorso.write_text(testo)
    percorso.chmod(0o755)


@pytest.fixture
def amb(tmp_path):
    """Environment + a bare remote with main, dev and a 2-commit gh-pages."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    scrivi_eseguibile(bin_dir / "pystub", STUB_PYTHON)
    scrivi_eseguibile(bin_dir / "curl", STUB_CURL)

    remoto = tmp_path / "remoto.git"
    git(tmp_path, "init", "--bare", "-b", "main", str(remoto))
    lavoro = tmp_path / "lavoro"
    git(tmp_path, "init", "-b", "main", str(lavoro))
    (lavoro / "README").write_text("main")
    git(lavoro, "add", "README")
    git(lavoro, "commit", "-m", "main 1")
    git(lavoro, "branch", "dev")
    git(lavoro, "checkout", "-q", "--orphan", "gh-pages")
    (lavoro / "README").write_text("vecchio sito 1")
    git(lavoro, "add", "README")
    git(lavoro, "commit", "-m", "sito 1")
    (lavoro / "README").write_text("vecchio sito 2")
    git(lavoro, "add", "README")
    git(lavoro, "commit", "-m", "sito 2")
    git(lavoro, "remote", "add", "origin", str(remoto))
    git(lavoro, "push", "-q", "origin", "main", "dev", "gh-pages")

    indice = tmp_path / "online" / "index.json"
    indice.parent.mkdir()
    indice.write_text('{"schema":1,"prezziDel":"2026-10-28T08:00:00+01:00","province":[]}')

    stato = tmp_path / "stato"
    env = {
        "PATH": f"{bin_dir}:/usr/bin:/bin",
        "HOME": str(tmp_path),
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
        "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1",
        "PIENOGIUSTO_PYTHON": str(bin_dir / "pystub"),
        "PIENOGIUSTO_STATO": str(stato),
        "PIENOGIUSTO_INDEX_URL": f"file://{indice}",
        "PUBBLICA_REMOTO": str(remoto),
        "STUB_CHIAMATE": str(tmp_path / "chiamate.txt"),
        "STUB_TELEGRAM": str(tmp_path / "telegram.txt"),
        "STUB_PREZZI_DEL": PREZZI_DEL,
    }
    return tmp_path, env, remoto, stato


def lancia(env, **extra):
    e = {**env, **extra}
    return subprocess.run(["bash", str(SCRIPT)], env=e, capture_output=True, text=True, timeout=60)


def passi(tmp_path):
    f = tmp_path / "chiamate.txt"
    return [r.split()[0] for r in f.read_text().splitlines()] if f.exists() else []


def telegram(tmp_path):
    f = tmp_path / "telegram.txt"
    return f.read_text().splitlines() if f.exists() else []


def rami(remoto):
    return git(remoto, "for-each-ref", "--format=%(refname) %(objectname)")


def rami_tranne_pages(remoto):
    return [r for r in rami(remoto).splitlines() if not r.startswith("refs/heads/gh-pages ")]


def tutto_il_testo(stato: Path):
    return "\n".join(p.read_text(errors="ignore") for p in stato.rglob("*") if p.is_file())


# ---- criterio 1: ordine dei passi e fail-closed -----------------------------------------------------------

def test_passi_in_ordine_test_build_contract(amb):
    tmp_path, env, remoto, stato = amb
    r = lancia(env, PUBBLICA="si")
    assert r.returncode == 0, r.stderr
    assert passi(tmp_path) == ["pytest", "build", "contract"]
    righe = (tmp_path / "chiamate.txt").read_text().splitlines()
    pytest_riga = righe[0]
    assert "test_spinta.py" in pytest_riga and "test_watchdog.py" in pytest_riga  # excluded from the run
    assert "--uscita" in righe[1]
    assert "--indice-precedente" in righe[1]


@pytest.mark.parametrize("passo,attesi", [
    ("pytest", ["pytest"]),
    ("build", ["pytest", "build"]),
    ("contract", ["pytest", "build", "contract"]),
])
def test_passo_fallito_ferma_tutto_senza_push(amb, passo, attesi):
    tmp_path, env, remoto, stato = amb
    prima = rami(remoto)
    r = lancia(env, PUBBLICA="si", STUB_FALLISCE=passo)
    assert r.returncode != 0
    assert passi(tmp_path) == attesi
    assert rami(remoto) == prima


# ---- criterio 2: gh-pages commit unico, force-with-lease solo su gh-pages ---------------------------------

def test_gh_pages_diventa_un_commit_unico_con_nojekyll(amb):
    tmp_path, env, remoto, stato = amb
    r = lancia(env, PUBBLICA="si")
    assert r.returncode == 0, r.stderr
    assert git(remoto, "rev-list", "--count", "gh-pages") == "1"
    file = git(remoto, "ls-tree", "-r", "--name-only", "gh-pages").splitlines()
    assert {".nojekyll", "index.json", "p/MI.json.gz"} <= set(file)
    assert "README" not in file  # old content gone: it is the site/ content, not a continuation
    assert "2026-10-29" in git(remoto, "log", "-1", "--format=%s", "gh-pages")


def test_main_e_altri_rami_del_remoto_non_cambiano(amb):
    tmp_path, env, remoto, stato = amb
    prima = rami_tranne_pages(remoto)
    assert len(prima) == 2  # main and dev
    r = lancia(env, PUBBLICA="si")
    assert r.returncode == 0, r.stderr
    assert rami_tranne_pages(remoto) == prima
    assert git(remoto, "rev-list", "--count", "main") == "1"


def test_primo_giro_senza_gh_pages_la_crea(amb):
    tmp_path, env, remoto, stato = amb
    git(remoto, "update-ref", "-d", "refs/heads/gh-pages")
    prima = rami_tranne_pages(remoto)
    r = lancia(env, PUBBLICA="si")
    assert r.returncode == 0, r.stderr
    assert git(remoto, "rev-list", "--count", "gh-pages") == "1"
    assert rami_tranne_pages(remoto) == prima


def test_push_che_fallisce_e_passo_pubblicazione_fallito(amb):
    tmp_path, env, remoto, stato = amb
    prima = rami(remoto)
    r = lancia(env, PUBBLICA="si", PUBBLICA_REMOTO=str(tmp_path / "non-esiste.git"))
    assert r.returncode != 0
    assert passi(tmp_path) == ["pytest", "build", "contract"]  # the failure is in the push, not before
    assert rami(remoto) == prima


# ---- criterio 3: stesso prezziDel online -> niente commit ne' push -----------------------------------------

@pytest.mark.parametrize("niente_site", ["0", "1"])
def test_stesso_prezzi_del_online_esce_0_senza_push(amb, niente_site):
    tmp_path, env, remoto, stato = amb
    (tmp_path / "online" / "index.json").write_text(
        '{"schema":1,"prezziDel":"%s","province":[]}' % PREZZI_DEL)
    prima = rami(remoto)
    r = lancia(env, PUBBLICA="si", STUB_NIENTE_SITE=niente_site)
    assert r.returncode == 0, r.stderr
    assert rami(remoto) == prima
    assert git(remoto, "rev-list", "--count", "gh-pages") == "2"
    assert telegram(tmp_path) == []


# ---- criterio 4: PUBBLICA=no (default) ---------------------------------------------------------------------

@pytest.mark.parametrize("extra", [{}, {"PUBBLICA": "no"}])
def test_pubblica_no_esegue_tutto_tranne_git(amb, extra):
    tmp_path, env, remoto, stato = amb
    prima = rami(remoto)
    r = lancia(env, **extra)
    assert r.returncode == 0, r.stderr
    assert "git saltato" in r.stdout
    assert passi(tmp_path) == ["pytest", "build", "contract"]
    assert rami(remoto) == prima
    assert (stato / "site" / "index.json").exists()


# ---- criterio 5: residui spostati, mai cancellati ----------------------------------------------------------

def test_log_e_uscita_precedenti_finiscono_in_residui_e_i_vecchi_in_vecchi(amb):
    tmp_path, env, remoto, stato = amb
    (stato / "site").mkdir(parents=True)
    (stato / "site" / "index.json").write_text("SITE-PRECEDENTE-MARKER")
    (stato / "pubblica.log").write_text("LOG-PRECEDENTE-MARKER")
    residui = stato / "residui"
    residui.mkdir()
    vecchio = residui / "giro-vecchio"
    vecchio.write_text("CONTENUTO-VECCHIO-MARKER")
    recente = residui / "giro-recente"
    recente.write_text("CONTENUTO-RECENTE-MARKER")
    ora = time.time()
    os.utime(vecchio, (ora - 10 * 86400, ora - 10 * 86400))
    os.utime(recente, (ora - 2 * 86400, ora - 2 * 86400))

    r = lancia(env)
    assert r.returncode == 0, r.stderr

    # previous log and previous output folder were moved, not deleted
    testo_residui = tutto_il_testo(residui)
    assert "LOG-PRECEDENTE-MARKER" in testo_residui
    assert "SITE-PRECEDENTE-MARKER" in testo_residui
    # fresh output built in place
    assert (stato / "site" / "index.json").exists()
    assert "SITE-PRECEDENTE-MARKER" not in (stato / "site" / "index.json").read_text()
    # older than 7 days -> residui/vecchi/, newer stays
    assert (residui / "vecchi" / "giro-vecchio").read_text() == "CONTENUTO-VECCHIO-MARKER"
    assert not vecchio.exists()
    assert recente.read_text() == "CONTENUTO-RECENTE-MARKER"
    assert not (residui / "vecchi" / "giro-recente").exists()


# ---- criterio 6: un solo Telegram su errore ----------------------------------------------------------------

def test_errore_invia_un_solo_telegram_senza_stampare_il_token(amb):
    tmp_path, env, remoto, stato = amb
    envfile = tmp_path / "telegram.env"
    envfile.write_text("TELEGRAM_BOT_TOKEN=SEGRETO123TOKEN\nTELEGRAM_CHAT_ID=424242\n")
    r = lancia(env, PIENOGIUSTO_ENV_FILE=str(envfile), STUB_FALLISCE="build")
    assert r.returncode != 0
    chiamate = telegram(tmp_path)
    assert len(chiamate) == 1
    assert "PienoGiusto dalla Pi: fallito al passo build" in chiamate[0].replace("%20", " ").replace("+", " ")
    assert "SEGRETO123TOKEN" not in r.stdout + r.stderr
    assert "SEGRETO123TOKEN" not in tutto_il_testo(stato)


def test_pubblicazione_fallita_invia_telegram_col_passo_pubblicazione(amb):
    tmp_path, env, remoto, stato = amb
    envfile = tmp_path / "telegram.env"
    envfile.write_text("TELEGRAM_BOT_TOKEN=SEGRETO123TOKEN\nTELEGRAM_CHAT_ID=424242\n")
    r = lancia(env, PUBBLICA="si", PUBBLICA_REMOTO=str(tmp_path / "non-esiste.git"),
               PIENOGIUSTO_ENV_FILE=str(envfile))
    assert r.returncode != 0
    chiamate = telegram(tmp_path)
    assert len(chiamate) == 1
    assert "fallito al passo pubblicazione" in chiamate[0].replace("%20", " ").replace("+", " ")


def test_senza_file_env_non_invia_lo_dice_in_log_e_l_exit_non_cambia(amb):
    tmp_path, env, remoto, stato = amb
    con = tmp_path / "telegram.env"
    con.write_text("TELEGRAM_BOT_TOKEN=SEGRETO123TOKEN\nTELEGRAM_CHAT_ID=424242\n")
    r_con = lancia(env, PIENOGIUSTO_ENV_FILE=str(con), STUB_FALLISCE="build")
    r_senza = lancia(env, PIENOGIUSTO_ENV_FILE=str(tmp_path / "non-esiste.env"), STUB_FALLISCE="build")
    assert r_senza.returncode != 0
    assert r_senza.returncode == r_con.returncode
    assert len(telegram(tmp_path)) == 1  # only the run WITH the env file sent one
    log = (stato / "pubblica.log").read_text() + r_senza.stdout + r_senza.stderr
    assert "Telegram non inviato" in log


def test_successo_non_invia_telegram(amb):
    tmp_path, env, remoto, stato = amb
    envfile = tmp_path / "telegram.env"
    envfile.write_text("TELEGRAM_BOT_TOKEN=SEGRETO123TOKEN\nTELEGRAM_CHAT_ID=424242\n")
    r = lancia(env, PUBBLICA="si", PIENOGIUSTO_ENV_FILE=str(envfile))
    assert r.returncode == 0, r.stderr
    assert telegram(tmp_path) == []


# ---- criterio 7: unita' systemd --user nel repo ------------------------------------------------------------

def valori(percorso: Path, chiave: str):
    assert percorso.exists(), f"{percorso} manca"
    out = []
    for riga in percorso.read_text().splitlines():
        riga = riga.strip()
        if riga.startswith(("#", ";")) or "=" not in riga:
            continue
        k, v = riga.split("=", 1)
        if k.strip() == chiave:
            out.append(v.strip())
    return out


def test_service_e_user_e_punta_a_pubblica_sh():
    (exec_start,) = valori(SERVICE, "ExecStart")
    assert exec_start.split()[-1].endswith("scripts/nodo-pi/pubblica.sh")
    assert valori(SERVICE, "User") == []  # --user unit: no User=
    assert valori(SERVICE, "Type") in ([], ["oneshot"])


def test_timer_orari_roma_random_delay_e_persistent():
    calendari = valori(TIMER, "OnCalendar")
    assert calendari
    assert all("Europe/Rome" in c for c in calendari)
    insieme = " ".join(calendari)
    for orario in ("09:15", "11:15", "13:15", "15:15", "18:15", "21:15"):
        assert orario in insieme, orario
    assert valori(TIMER, "RandomizedDelaySec") == ["2min"]
    assert valori(TIMER, "Persistent") == ["true"]
    assert valori(TIMER, "WantedBy") == ["timers.target"]


# ---- criterio 8: decisione documentata ---------------------------------------------------------------------

def sezione_decisione() -> str:
    righe = DECISIONI.read_text().splitlines()
    inizio = next((i for i, r in enumerate(righe)
                   if r.startswith("#") and "pubblicazione dal nodo di casa" in r.lower()), None)
    assert inizio is not None, "manca la decisione «pubblicazione dal nodo di casa, Pages da branch gh-pages»"
    fine = len(righe)
    for j in range(inizio + 1, len(righe)):
        if righe[j].startswith(("# ", "## ", "### ")):
            fine = j
            break
    return "\n".join(righe[inizio:fine])


def test_decisioni_ha_la_nuova_decisione_con_motivo_alternative_e_rischio():
    testo = sezione_decisione()
    basso = testo.lower()
    assert "pages da branch gh-pages" in basso
    assert "timeout" in basso and "mimit" in basso and "runner" in basso      # motivo
    assert "self-hosted" in basso and "node" in basso                          # alternativa 1
    assert "oidc" in basso                                                     # alternativa 2
    assert "crescita" in basso and "commit unico" in basso                     # rischio risolto
    assert "systemctl --user" in basso                                         # comandi di installazione
