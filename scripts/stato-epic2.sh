#!/usr/bin/env bash
# Stato dei 3 criteri di «Epic 2 go-live chiuso», contati dai log.
# Uso: bash scripts/stato-epic2.sh [DIR]   (DIR default: $PIENOGIUSTO_STATO o ~/.local/state/azienda/pienogiusto)
# STATO_EPIC2_OGGI=YYYY-MM-DD fissa "oggi". Finestra: gli ultimi 7 giorni, oggi incluso.
# Exit 0 solo se tutti e 3 i criteri sono OK, altrimenti 1.
set -u

DIR="${1:-${PIENOGIUSTO_STATO:-$HOME/.local/state/azienda/pienogiusto}}"
OGGI="${STATO_EPIC2_OGGI:-$(date +%F)}"

pubblicati=0
verificati=0
for i in 0 1 2 3 4 5 6; do
  giorno="$(date -d "$OGGI -$i day" +%F)"
  compatto="${giorno//-/}"

  # criterio 1: almeno un log del giorno con pubblicazione riuscita e senza ERRORE
  for log in "$DIR"/residui/pubblica.log."$compatto"-*; do
    [ -f "$log" ] || continue
    if grep -qE "gh-pages pubblicato|gia' online" "$log" && ! grep -q "ERRORE" "$log"; then
      pubblicati=$((pubblicati + 1))
      break
    fi
  done

  # criterio 2: riga OK per il giorno e nessun KO
  if [ -f "$DIR/verifica-url.log" ] \
     && grep -qx "$giorno OK" "$DIR/verifica-url.log" \
     && ! grep -qx "$giorno KO" "$DIR/verifica-url.log"; then
    verificati=$((verificati + 1))
  fi
done

# criterio 3: ultima riga del watchdog = "attivo" di oggi o ieri
watchdog_ok=0
ultima=""
if [ -f "$DIR/watchdog.log" ]; then
  while IFS= read -r riga; do
    [ -n "$riga" ] && ultima="$riga"
  done < "$DIR/watchdog.log"
fi
ieri="$(date -d "$OGGI -1 day" +%F)"
if [ "$ultima" = "$OGGI attivo" ] || [ "$ultima" = "$ieri attivo" ]; then
  watchdog_ok=1
fi

esito=0
stato() { # numero ok dettaglio
  if [ "$2" = 1 ]; then echo "criterio $1: OK $3"; else echo "criterio $1: NO $3"; esito=1; fi
}

stato 1 "$([ "$pubblicati" -eq 7 ] && echo 1 || echo 0)" "- pubblicazione dalla Pi: $pubblicati/7 giorni"
stato 2 "$([ "$verificati" -eq 7 ] && echo 1 || echo 0)" "- verifica URL pubblico: $verificati/7 OK"
stato 3 "$watchdog_ok" "- watchdog attivo (ultima riga: ${ultima:-assente})"

exit "$esito"
