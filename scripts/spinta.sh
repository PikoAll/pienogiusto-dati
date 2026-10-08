#!/usr/bin/env bash
# Pushes the publish workflow when the expected prices are missing.
#
# GitHub starts the scheduled runs of pubblica.yml 5-9 h late. This script, run by a systemd user
# timer on an always-on machine (pienogiusto-dati-spinta.timer), reads the PUBLISHED index.json and,
# if prezziDel is two days old or more (the price file of yesterday is the one expected today), launches
# the workflow by hand. The workflow itself deploys only when prezziDel is new, so a useless push
# changes nothing. No commits, no deletions, idempotent.
#
# Guards: no launch while a run is queued/in progress; no launch within 2 h of the previous one.
# Exit: 0 done (launched or not); 1 index unreachable/invalid or gh error; 2 bad argument.
# One line per run in the log: time, prezziDel, action.
#
#   spinta.sh           one round
#   spinta.sh --prova   print what it would do, launch nothing, write nothing
set -euo pipefail

REPO="${PIENOGIUSTO_REPO:-PikoAll/pienogiusto-dati}"
WORKFLOW="pubblica.yml"
INDEX_URL="${PIENOGIUSTO_INDEX_URL:-https://pikoall.github.io/pienogiusto-dati/index.json}"
LOG="${PIENOGIUSTO_SPINTA_LOG:-$HOME/.local/state/pienogiusto/spinta.log}"
STATO="${PIENOGIUSTO_SPINTA_STATO:-$HOME/.local/state/pienogiusto/spinta.ultimo}"
OGGI="${PIENOGIUSTO_OGGI:-$(date +%F)}"
PAUSA_SECONDI=$((2 * 3600))

PROVA=0
case "${1:-}" in
  "") ;;
  --prova) PROVA=1 ;;
  *) echo "uso: $0 [--prova]" >&2; exit 2 ;;
esac

diario() {
  if [ "$PROVA" = 1 ]; then echo "[prova] $*"; return; fi
  mkdir -p "$(dirname "$LOG")"
  printf '%s %s\n' "$(date -Is)" "$*" >> "$LOG"
}

if ! json=$(curl -fsS --max-time 20 "$INDEX_URL" 2>&1); then
  diario "ERRORE index ($INDEX_URL): ${json//$'\n'/ }"
  exit 1
fi
if ! prezzi_del=$(printf '%s' "$json" | python3 -c 'import json,sys; print(json.load(sys.stdin)["prezziDel"])' 2>&1); then
  diario "ERRORE index senza prezziDel valido"
  exit 1
fi

giorno="${prezzi_del:0:10}"
limite=$(date -d "$OGGI -2 day" +%F)
if [[ "$giorno" > "$limite" ]]; then
  diario "prezziDel=$giorno azione=nessuna (non lancio: dato atteso gia' presente)"
  exit 0
fi

if ! in_corso=$(gh run list --workflow "$WORKFLOW" -R "$REPO" -L 20 --json status \
    --jq '[.[] | select(.status == "in_progress" or .status == "queued")] | length' 2>&1); then
  diario "ERRORE gh run list ($REPO): ${in_corso//$'\n'/ }"
  exit 1
fi
if [ "$in_corso" != 0 ]; then
  diario "prezziDel=$giorno azione=giro-in-corso (non lancio: c'e' gia' un giro)"
  exit 0
fi

ultimo=0
[ -f "$STATO" ] && ultimo=$(cat "$STATO")
if [ $(( $(date +%s) - ultimo )) -lt "$PAUSA_SECONDI" ]; then
  diario "prezziDel=$giorno azione=lancio-recente (non lancio: ultimo lancio < 2 h fa)"
  exit 0
fi

if [ "$PROVA" = 1 ]; then
  echo "lancerei: gh workflow run $WORKFLOW -R $REPO (prezziDel=$giorno, oggi=$OGGI)"
  exit 0
fi

if ! out=$(gh workflow run "$WORKFLOW" -R "$REPO" 2>&1); then
  diario "ERRORE lancio ($REPO): ${out//$'\n'/ }"
  exit 1
fi
mkdir -p "$(dirname "$STATO")"
date +%s > "$STATO"
diario "prezziDel=$giorno azione=lanciato"
