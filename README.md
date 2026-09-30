# pienogiusto-dati

Ogni mattina scarica gli open data carburanti del MIMIT, li valida e pubblica su GitHub Pages
un JSON compresso per provincia, letto dall'app Android **PienoGiusto**.

- `index.json`: elenco province con file, numero impianti e riquadro geografico.
- `p/<SIGLA>.json.gz`: impianti della provincia con i prezzi.
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
Da installare **dopo il primo deploy verde**:

```bash
mkdir -p ~/.config/systemd/user
ln -s ~/Scrivania/progetti/pienogiusto-dati/scripts/systemd/pienogiusto-watchdog.service ~/.config/systemd/user/
ln -s ~/Scrivania/progetti/pienogiusto-dati/scripts/systemd/pienogiusto-watchdog.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now pienogiusto-watchdog.timer
systemctl --user start pienogiusto-watchdog.service && tail -n 1 ~/.local/state/pienogiusto-watchdog.log
loginctl show-user "$USER" -p Linger   # Linger=no: il timer gira solo con la sessione aperta
```

## Licenze
- **Codice**: MIT, vedi [LICENSE](LICENSE).
- **Dati**: NON sono coperti dalla licenza MIT. Sono del MIMIT e restano sotto IODL 2.0 (sotto).

## Fonte e licenza dei dati
Dati: **Ministero delle Imprese e del Made in Italy (MIMIT)**, dataset
[Carburanti - Prezzi praticati e anagrafica degli impianti](https://www.mimit.gov.it/it/open-data/elenco-dataset/carburanti-prezzi-praticati-e-anagrafica-degli-impianti),
rilasciati con licenza [Italian Open Data License v2.0 (IODL 2.0)](https://www.dati.gov.it/iodl/2.0/).
I dati pubblicati qui sono filtrati, uniti e riformattati; il MIMIT non e' responsabile di queste elaborazioni.
