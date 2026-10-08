# Stato e Checkpoint (diario di bordo)
Regola: aggiunge una voce IN TESTA solo l'agente che chiude il ticket.

## [2026-10-08] Pubblicazione affidabile: cron in piu' e spinta dal mini PC (branch `ci/orari-pubblicazione`)
- GitHub avvia i cron 5-9 h in ritardo: aggiunti `15 11`, `15 13`, `15 16`, `15 19` UTC a `pubblica.yml` (un giro senza `prezziDel` nuovo non pubblica).
- `scripts/spinta.sh` + timer utente `pienogiusto-dati-spinta` (09:40, 10:40, 12:10, 14:10, 17:10 ora italiana): se `prezziDel` ha 2 giorni o piu' lancia `gh workflow run`; pausa di 2 h, mai con un giro in corso. 11 test nuovi, 143 verdi.
- Il watchdog (`scripts/watchdog.sh`, timer 10:30) e' installato e attivo dal 2026-09-30 ma guarda solo che il workflow sia attivo: non controlla l'eta' dei dati e non ha un canale di avviso (APERTO: avviso Telegram se spinta va in ERRORE o `prezziDel` supera 3 giorni).

## [2026-10-04] Elenco nazionale dei comuni (branch `feat/comuni`, PR verso main)
- `comuni.json.gz` + chiave `comuni` in `index.json` (schema resta 1); modulo `pienogiusto_dati/comuni.py`.
- Cancelli nuovi `comuni` (>= 5.000), `comuni_bbox`, `comuni_nome_vuoto` (D12). 132 test verdi, actionlint e rete di sicurezza verdi.
- Prova con dati veri (prezzi del 2026-10-03): 21.667 impianti, 5.286 comuni, 87 KB gz; MONOPOLI/BA k=15, lat 40.94025 lon 17.27184.
- Merge lo fa Giuseppe dopo la CI verde; poi il mandato F dell'app (`ComuniRepository`) legge il file.

## [2026-09-30] Giro 2
- Cancelli nuovi: `dati_fermi` (niente ripubblicazione se `prezziDel` non avanza, rosso oltre 3 giorni) e `codifica` (U+FFFD > 0,1%).
- Keepalive tolto; watchdog `scripts/watchdog.sh` + timer systemd utente (NON installato). LICENSE MIT per il codice.
- actionlint 1.7.12 pulito. Dominio: nessun sito utente, URL `https://pikoall.github.io/pienogiusto-dati/`.

## [2026-09-30] Inizializzazione
- Ricognizione dati reali (docs/RICOGNIZIONE.md), pipeline completa, 89 test verdi, rete di sicurezza verde.
- Prova end-to-end con dati veri: 21.681 impianti, 107 province, 1,52 MB gzip totali, BA 25 KB, 4,7 s.
- Da fare: repo GitHub, Pages, primo lancio (comandi nella relazione a Giuseppe). Rischi aperti in DECISIONI.md.
