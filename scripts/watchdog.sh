#!/usr/bin/env bash
# Watchdog for the scheduled workflow pubblica.yml (replaces the keepalive, see docs/DECISIONI.md).
#
# GitHub disables scheduled workflows of public repos after 60 days without repository
# activity (state "disabled_inactivity"). This script, run daily by a systemd user timer,
# re-enables it and launches a run. No commits, no deletions, idempotent.
#
# Exit: 0 active or re-enabled; 1 gh error or unexpected state (e.g. disabled by hand:
# left alone on purpose). One line per run in the log.
set -euo pipefail

REPO="${PIENOGIUSTO_REPO:-PikoAll/pienogiusto-dati}"
WORKFLOW="pubblica.yml"
LOG="${PIENOGIUSTO_WATCHDOG_LOG:-$HOME/.local/state/pienogiusto-watchdog.log}"

mkdir -p "$(dirname "$LOG")"
diario() { printf '%s %s\n' "$(date -Is)" "$*" >> "$LOG"; }

if ! stato=$(gh api "repos/$REPO/actions/workflows/$WORKFLOW" --jq .state 2>&1); then
  diario "ERRORE gh api ($REPO): ${stato//$'\n'/ }"
  exit 1
fi

case "$stato" in
  active)
    diario "OK $REPO $WORKFLOW stato=active"
    ;;
  disabled_inactivity)
    if ! out=$(gh workflow enable "$WORKFLOW" -R "$REPO" 2>&1); then
      diario "ERRORE riattivazione ($REPO): ${out//$'\n'/ }"
      exit 1
    fi
    if ! out=$(gh workflow run "$WORKFLOW" -R "$REPO" 2>&1); then
      diario "ERRORE lancio dopo riattivazione ($REPO): ${out//$'\n'/ }"
      exit 1
    fi
    diario "RIATTIVATO $REPO $WORKFLOW (era disabled_inactivity) e lanciato un run"
    ;;
  *)
    diario "ATTENZIONE $REPO $WORKFLOW stato=$stato: non lo tocco (disattivato a mano?)"
    exit 1
    ;;
esac
