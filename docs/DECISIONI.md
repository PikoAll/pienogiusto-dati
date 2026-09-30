# Decisioni — pienogiusto-dati

## Prese (2026-09-30)

> **Approvazione (giro 2, 2026-09-30):** Cowork ha approvato gli scostamenti D1 (cron 07:15/09:15 UTC),
> D2 (cancello prezzi a quota 0,5%) e D4 (parser a mano) proposti nel giro 1.

### D1 · Orari del cron: 07:15 e 09:15 UTC (non 06:15 e 09:15 ora italiana) — approvata da Cowork
Il prompt chiedeva 06:15 e 09:15 ora italiana. Misura reale: `prezzo_alle_8.csv` ha
`Last-Modified: 06:45 UTC` (08:45 a Roma). Un run alle 06:15 ripubblica **sempre** i dati di ieri: e' un run inutile.
GitHub usa UTC senza ora legale, quindi un orario fisso si sposta di un'ora d'inverno.
- 07:15 UTC = 09:15 estate / 08:15 inverno (d'inverno forse ancora prima dell'aggiornamento MIMIT);
- 09:15 UTC = 11:15 estate / 10:15 inverno: run di sicurezza, prende sempre il dato nuovo.
Ripubblicare lo stesso dato e' innocuo. Da rivedere dopo qualche settimana guardando i `prezziDel` pubblicati
(i cron di GitHub possono anche partire in ritardo di decine di minuti).

### D2 · Cancello prezzi: quota, non "tutti fra 0,3 e 4,0" — approvata da Cowork
Letto alla lettera il cancello sarebbe rosso **ogni giorno**: il file reale ha sempre qualche prezzo assurdo
(12 righe il 2026-09-29: 0,100 · 8,888 …). Un cancello sempre rosso viene spento, non rispettato.
Quindi: la singola riga fuori 0,3–4,0 si scarta e si conta (`report.json`); la pubblicazione si blocca se le
righe fuori range superano lo 0,5% (oggi 0,013%, margine x38). Nei file pubblicati nessun prezzo e' fuori range
(lo verifica il test di contratto sul build vero).

### D3 · Cancelli aggiuntivi
- `coordinate_italia`: nessun impianto pubblicato fuori dal riquadro (difesa in profondita', oggi 0).
- `righe_anagrafica` / `righe_prezzi`: righe illeggibili <= 0,5% per file (prende i cambi di formato parziali
  e i file troncati che l'HTTP non ha segnalato).
- Test di contratto eseguito sul `site/` vero nel workflow, prima dell'upload.

### D4 · Parser senza modulo `csv` — approvata da Cowork
Il file non usa quoting e ha virgolette sbilanciate: il modulo `csv` fonde righe in silenzio. Divisione manuale
sul separatore + recupero delle righe con separatori in piu' (vedi RICOGNIZIONE.md).

### D5 · `t` senza offset
Il contratto d'esempio scrive `"t": "2026-09-28T19:12:00"` (ora locale di Roma, senza offset). Il contratto e'
vincolante, quindi niente offset; `prezziDel` invece ha l'offset (come nell'esempio).

### D6 · `site/` scritto in modo atomico
Build in `site.in-corso/` e rinomina finale: `site/` esiste completo o non esiste. Se `site/` esiste gia' lo script
si rifiuta (exit 2) invece di sovrascrivere.

### D7 · Attribuzione IODL anche nel sito pubblicato
`LEGGIMI.txt` in `site/` con fonte, licenza e nota di elaborazione: chi scarica i JSON senza passare dal repo
vede comunque l'attribuzione richiesta dalla IODL 2.0.

### D8 · Cancello "dati fermi" (giro 2)
- `prezziDel` nuovo <= quello pubblicato -> **niente di nuovo**: exit 0, nessun `site/`, `nuovo=false` in
  `$GITHUB_OUTPUT`, niente deploy. Cosi' i run prima dell'aggiornamento MIMIT (e il secondo run del giorno)
  non ripubblicano lo stesso dato.
- Stesso caso, ma il `prezziDel` pubblicato ha piu' di **3 giorni** rispetto all'ora del run -> **rosso**
  (exit 1, cancello `dati_fermi`): GitHub manda la mail. In condizioni normali l'eta' al run e' ~25 h;
  3 giorni = MIMIT fermo da 2 giorni.
- Dato nuovo ma comunque vecchio (>3 giorni): si pubblica lo stesso, perche' migliora quello che c'e' online.
- Senza indice precedente leggibile (primo giro) si pubblica.

### D9 · Cancello "codifica" (giro 2)
Righe con `�` (U+FFFD) dopo la decodifica > **0,1%** per file -> rosso. Misurato sui file reali del 2026-09-29:
**0 righe** su 23.940 e su 92.909. Prende sia il fallback cp1252 con byte non definiti sia un file gia' rovinato
all'origine (UTF-8 che contiene U+FFFD).

### D10 · Keepalive tolto, watchdog al suo posto (giro 2)
Il job `keepalive` (riattivazione via API da dentro il workflow) e' stato **tolto**: nessuna prova che azzeri il
contatore dei 60 giorni (vedi R1), e un workflow gia' disattivato non gira, quindi non puo' riattivarsi da solo.
Al suo posto `scripts/watchdog.sh` + timer systemd utente (ogni giorno 10:30, `Persistent=true`), scelto da Cowork:
gira FUORI da GitHub, legge lo stato di `pubblica.yml`, se e' `disabled_inactivity` lo riattiva e lancia un run.
Nessun commit automatico. Se lo stato e' `disabled_manually` non lo tocca (e va in rosso nel diario).
Installazione solo dopo il primo deploy verde (comandi nel README).

### D11 · Dominio di GitHub Pages (giro 2)
Controllato il 2026-09-30 con `gh api`:
- non esiste un sito utente `PikoAll/PikoAll.github.io` (404);
- `pikobit.it` e' il dominio personalizzato del sito di **progetto** `mySiteWeb`
  (`www.traslochimalusardi.it` quello di `traslochimalusardi-web`).
Secondo la documentazione GitHub i siti di progetto ereditano solo il dominio del **sito utente**; il dominio di un
altro sito di progetto non si propaga. Quindi l'URL reale e':
**`https://pikoall.github.io/pienogiusto-dati/index.json`** — niente contenuti carburanti sotto pikobit.it.
Attenzione per il futuro: se un giorno il sito Pikobit venisse spostato in un repo `PikoAll.github.io` con dominio
`pikobit.it`, questo sito passerebbe **automaticamente** a `pikobit.it/pienogiusto-dati/` (e l'app punterebbe a un
URL che fa redirect). In quel caso: dominio proprio per questo repo o organizzazione GitHub separata.
https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/about-custom-domains-and-github-pages

## Rischi aperti

### R1 · Spegnimento del workflow dopo 60 giorni — MITIGATO dal watchdog (D10), resta un rischio residuo
Residuo: il watchdog gira solo se la macchina e' accesa, il timer e' installato e `gh` e' autenticato; tra lo
spegnimento e il run del watchdog passano al massimo ~24 h (piu' il tempo di macchina spenta).
Ricerca del giro 1 (perche' il keepalive via API e' stato tolto):
- La documentazione GitHub dice solo: nei repo pubblici i workflow schedulati si disattivano dopo 60 giorni
  senza attivita' nel repository. **Non dice** che la riattivazione via API (`PUT .../workflows/{id}/enable`)
  azzeri il contatore.
  https://docs.github.com/en/actions/managing-workflow-runs-and-deployments/managing-workflow-runs/disabling-and-enabling-a-workflow
- `efrecon/gh-action-keepalive` scrive che la sua prima versione (disattiva/riattiva i workflow) "non riusciva a
  superare la scadenza di GitHub" ed e' passata ai commit. https://github.com/efrecon/gh-action-keepalive
- Il repo `gautamkrishnar/keepalive-workflow` (quello con la "modalita' API") oggi risulta **disabilitato da
  GitHub Staff per violazione dei termini di servizio**: non si puo' piu' consultare.
- Discussione della community senza risposta ufficiale: https://github.com/orgs/community/discussions/184653
- Scelta di Cowork (giro 2): watchdog esterno, niente commit automatici. In piu' il cancello `dati_fermi` (D8)
  manda una mail se i dati online invecchiano oltre 3 giorni.

### R2 · Codifica — chiuso dal cancello D9
Oggi UTF-8; cp1252 gestito. Resta scoperto solo un file in una codifica a 8 bit diversa (es. latin-9) che
decodificata in cp1252 non produce `�` ma lettere sbagliate: improbabile, nessun cancello lo vede.

### R3 · Formato vecchio con virgola
Supportato per intestazioni e separatore, ma con la virgola un indirizzo che contiene una virgola e' ambiguo
(non si sa se va nel nome o nell'indirizzo). Accettato: il formato attuale e' `|` dal 2026-02-10.

### R4 · Stesso dato due volte / dato vecchio — chiuso dal cancello D8

### R5 · Primo giro e indice irraggiungibile
Se l'`index.json` pubblicato non si legge (primo giro, Pages giu'), il cancello ±10% degrada alla soglia
assoluta >= 18.000. Scelta del prompt; il log lo dichiara ("indice precedente non disponibile").

### R6 · Versioni delle action
`checkout@v5`, `setup-python@v6`, `configure-pages@v5`, `upload-pages-artifact@v4`, `deploy-pages@v4`:
controllare al primo run che non ci siano avvisi di deprecazione. `actionlint` 1.7.12 (binario ufficiale,
checksum verificato, in `~/.local/bin`) passa pulito sui due workflow. `shellcheck` non e' installato: actionlint
non ha controllato il contenuto degli script `run:`.
