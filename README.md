# pienogiusto-dati

Ogni mattina scarica gli open data carburanti del MIMIT, li valida e pubblica su GitHub Pages
un JSON compresso per provincia, letto dall'app Android **PienoGiusto**.

- `index.json`: elenco province con file, numero impianti e riquadro geografico.
- `p/<SIGLA>.json.gz`: impianti della provincia con i prezzi.
- `comuni.json.gz`: elenco nazionale dei comuni (nome, provincia, coordinate medie, numero impianti) per la
  ricerca senza GPS.
- `report.json`: conteggi, scarti per motivo, esito dei cancelli.

Formato: [docs/CONTRATTO.md](docs/CONTRATTO.md). Se un controllo fallisce non si pubblica nulla
e restano online i dati del giorno prima. Se il MIMIT non ha ancora aggiornato, non si ripubblica;
se i dati online hanno piu' di 3 giorni il job va in rosso (mail di GitHub).

```bash
python -m pienogiusto_dati.pubblica --uscita site      # dati veri
pip install -r requirements-test.txt && pytest -q        # test
```

## Watchdog (timer utente, sulla macchina sempre accesa)
GitHub spegne i workflow schedulati dopo 60 giorni senza attivita' nel repo. `scripts/watchdog.sh`
controlla ogni giorno alle 10:30 lo stato di `pubblica.yml`; se e' `disabled_inactivity` lo riattiva
e lancia un run. Diario: `~/.local/state/pienogiusto-watchdog.log`. Serve `gh` autenticato come PikoAll.
Installato e attivo sul mini PC (verificato il 2026-10-03: timer `enabled`/`active`, diario con
`stato=active`). Installazione su una macchina nuova:

```bash
mkdir -p ~/.config/systemd/user
ln -s ~/Scrivania/progetti/pienogiusto-dati/scripts/systemd/pienogiusto-watchdog.service ~/.config/systemd/user/
ln -s ~/Scrivania/progetti/pienogiusto-dati/scripts/systemd/pienogiusto-watchdog.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now pienogiusto-watchdog.timer
systemctl --user start pienogiusto-watchdog.service && tail -n 1 ~/.local/state/pienogiusto-watchdog.log
loginctl show-user "$USER" -p Linger   # Linger=no: il timer gira solo con la sessione aperta
```

## Spinta della pubblicazione (timer utente, stessa macchina)
I cron di GitHub partono 5-9 h in ritardo. `scripts/spinta.sh` legge l'`index.json` pubblicato alle
09:40, 10:40, 12:10, 14:10 e 17:10 (ora italiana); se `prezziDel` e' di due giorni fa o piu' vecchio
(manca il dato atteso oggi), non c'e' un giro in corso e l'ultimo lancio e' di piu' di 2 h fa, lancia
`gh workflow run pubblica.yml`. Il workflow pubblica solo con `prezziDel` nuovo, quindi una spinta
inutile non cambia nulla. Diario: `~/.local/state/pienogiusto/spinta.log`. Prova a secco:
`scripts/spinta.sh --prova`. Installazione (come il watchdog, con `pienogiusto-dati-spinta.*`):

```bash
ln -s ~/Scrivania/progetti/pienogiusto-dati/scripts/systemd/pienogiusto-dati-spinta.service ~/.config/systemd/user/
ln -s ~/Scrivania/progetti/pienogiusto-dati/scripts/systemd/pienogiusto-dati-spinta.timer ~/.config/systemd/user/
systemctl --user daemon-reload && systemctl --user enable --now pienogiusto-dati-spinta.timer
```

Il watchdog sopra NON controlla l'eta' dei dati: guarda solo che il workflow sia attivo.

## Controlli

- Test: `pip install -r requirements-test.txt && pytest -q` (132 test verdi il 2026-10-04).
- CI reale: `.github/workflows/ci.yml` su ogni push e pull request (`pytest -q`, Python 3.12,
  ubuntu-24.04). `pubblica.yml` e' la pubblicazione giornaliera (cron + avvio manuale), non la CI.
- Workflow modificati: `actionlint .github/workflows/*.yml` prima della PR.
- Rete di sicurezza: `python3 ~/Scrivania/arsenale-ai/scripts/verifica-rete-di-sicurezza.py .`
  (0 = verde; nessuna esenzione in `.rete-di-sicurezza.json`).

## Regole git e passaggi di consegne

- Mai su `main`: ramo + PR. Merge solo dopo la verifica di Cowork (`Esito: OK`) e l'ok scritto di
  Giuseppe; mai `--delete-branch`, mai `push --force`. Lotto di card non abilitato.
- Il contratto con l'app (`docs/CONTRATTO.md`, test in `tests/contract/`) non si cambia senza alzare
  `schema`: regole complete in `CLAUDE.md`.
- Mandati e resoconti: `~/Scrivania/prompt/<AAAA-MM-GG>_<task>/` (01-prompt, 02-resoconto,
  03-verifica). Diario del progetto: `docs/5_stato_e_checkpoint.md`; decisioni: `docs/DECISIONI.md`.

## Licenze
- **Codice**: MIT, vedi [LICENSE](LICENSE).
- **Dati**: NON sono coperti dalla licenza MIT. Sono del MIMIT e restano sotto IODL 2.0 (sotto).

## Fonte e licenza dei dati
Dati: **Ministero delle Imprese e del Made in Italy (MIMIT)**, dataset
[Carburanti - Prezzi praticati e anagrafica degli impianti](https://www.mimit.gov.it/it/open-data/elenco-dataset/carburanti-prezzi-praticati-e-anagrafica-degli-impianti),
rilasciati con licenza [Italian Open Data License v2.0 (IODL 2.0)](https://www.dati.gov.it/iodl/2.0/).
I dati pubblicati qui sono filtrati, uniti e riformattati; il MIMIT non e' responsabile di queste elaborazioni.
