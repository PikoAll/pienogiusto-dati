#!/usr/bin/env bash
# Publishes the PienoGiusto data from the home node (Raspberry Pi), run by azienda-pienogiusto.timer.
#
# Steps, in order, fail-closed (a failed step stops everything, exit 1, no push):
#   test -> build (download + gates, output in $PIENOGIUSTO_STATO/site) -> contract -> pubblicazione
# Publication: gh-pages becomes ONE orphan commit with the content of site/ plus .nojekyll, pushed with
# --force-with-lease ONLY on gh-pages (never on other branches). If the online index.json already has the same
# prezziDel nothing is committed or pushed.
#
# Environment (all optional):
#   PUBBLICA=si|no            enable the git part (default no: prints "git saltato")
#   PUBBLICA_REMOTO           remote URL/path to push to (set by the unit, e.g. git@github-pienogiusto:...)
#   PIENOGIUSTO_PYTHON        interpreter (default python3)
#   PIENOGIUSTO_STATO         state dir (default ~/.local/state/azienda/pienogiusto): pubblica.log, site/, residui/
#   PIENOGIUSTO_INDEX_URL     online index.json (default the Pages one)
#   PIENOGIUSTO_ENV_FILE      env file with TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID
#                             (default ~/.config/azienda/telegram.env); missing file = no Telegram, said in the log
# Nothing is ever deleted: leftovers are moved to residui/, the ones older than 7 days to residui/vecchi/.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/../.."

PY="${PIENOGIUSTO_PYTHON:-python3}"
STATO="${PIENOGIUSTO_STATO:-$HOME/.local/state/azienda/pienogiusto}"
INDEX_URL="${PIENOGIUSTO_INDEX_URL:-https://pikoall.github.io/pienogiusto-dati/index.json}"
ENV_FILE="${PIENOGIUSTO_ENV_FILE:-$HOME/.config/azienda/telegram.env}"
PUBBLICA="${PUBBLICA:-no}"
REMOTO="${PUBBLICA_REMOTO:-}"
SITE="$STATO/site"
LOG="$STATO/pubblica.log"
RESIDUI="$STATO/residui"
ORA="$(date +%Y%m%d-%H%M%S)-$$"

unset PIENOGIUSTO_SITE

# ---- residues: previous log and output dir are moved, never deleted ----
mkdir -p "$RESIDUI/vecchi"
[ -e "$LOG" ] && mv "$LOG" "$RESIDUI/pubblica.log.$ORA"
[ -e "$SITE" ] && mv "$SITE" "$RESIDUI/site.$ORA"
find "$RESIDUI" -mindepth 1 -maxdepth 1 -not -name vecchi -mtime +7 -exec mv -t "$RESIDUI/vecchi" {} +

exec > >(tee -a "$LOG") 2>&1

PASSO="preparazione"

notifica() {
  local passo="$1" token="" chat=""
  if [ ! -f "$ENV_FILE" ]; then
    echo "Telegram non inviato: file env assente ($ENV_FILE)"
    return 0
  fi
  token="$(sed -n 's/^TELEGRAM_BOT_TOKEN=//p' "$ENV_FILE")"
  chat="$(sed -n 's/^TELEGRAM_CHAT_ID=//p' "$ENV_FILE")"
  if [ -z "$token" ] || [ -z "$chat" ]; then
    echo "Telegram non inviato: token o chat mancanti nel file env"
    return 0
  fi
  if curl -s --max-time 20 -o /dev/null -d "chat_id=$chat" \
      --data-urlencode "text=PienoGiusto dalla Pi: fallito al passo $passo" \
      "https://api.telegram.org/bot${token}/sendMessage"; then
    echo "Telegram inviato"
  else
    echo "Telegram non inviato: errore di rete"
  fi
}

alla_fine() {
  local rc=$?
  trap - EXIT
  if [ "$rc" -ne 0 ]; then
    echo "ERRORE: fallito al passo $PASSO (exit $rc)"
    notifica "$PASSO" || true
  fi
  exit "$rc"
}
trap alla_fine EXIT

prezzi_del() {  # reads an index.json on stdin, prints prezziDel
  "$PY" -c 'import json,sys; print(json.load(sys.stdin)["prezziDel"])'
}

PASSO="test"
echo "== $PASSO"
"$PY" -m pytest -q --ignore=tests/integration/test_spinta.py --ignore=tests/integration/test_watchdog.py

PASSO="build"
echo "== $PASSO"
"$PY" -m pienogiusto_dati.pubblica --uscita "$SITE" --indice-precedente "$INDEX_URL"
if [ ! -f "$SITE/index.json" ]; then
  echo "Nessun sito nuovo da pubblicare."
  exit 0
fi

PASSO="contract"
echo "== $PASSO"
PIENOGIUSTO_SITE="$SITE" "$PY" -m pytest -q tests/contract

PASSO="pubblicazione"
echo "== $PASSO"
if [ "$PUBBLICA" != "si" ]; then
  echo "git saltato (PUBBLICA=$PUBBLICA)"
  exit 0
fi

nuovo="$(prezzi_del < "$SITE/index.json")"
online=""
if json="$(curl -fsS --max-time 20 "$INDEX_URL" 2>/dev/null)"; then
  online="$(printf '%s' "$json" | prezzi_del 2>/dev/null || true)"
fi
if [ -n "$online" ] && [ "$online" = "$nuovo" ]; then
  echo "prezziDel $nuovo gia' online: niente da pubblicare."
  exit 0
fi

[ -n "$REMOTO" ] || { echo "PUBBLICA_REMOTO non impostato"; exit 1; }

# Expected sha of the remote gh-pages (empty = branch absent), used as the lease.
atteso="$(git ls-remote --heads "$REMOTO" refs/heads/gh-pages | cut -f1)"

PAGES="$RESIDUI/pages.$ORA"
mkdir -p "$PAGES"
cp -a "$SITE/." "$PAGES/"
touch "$PAGES/.nojekyll"
git -C "$PAGES" init -q -b gh-pages
git -C "$PAGES" add -A
git -C "$PAGES" -c user.name="PienoGiusto Pi" -c user.email="pienogiusto-pi@localhost" \
  commit -q -m "prezziDel $nuovo (Raspberry Pi)"
git -C "$PAGES" push -q --force-with-lease="gh-pages:$atteso" "$REMOTO" gh-pages:refs/heads/gh-pages
echo "gh-pages pubblicato: prezziDel $nuovo"
