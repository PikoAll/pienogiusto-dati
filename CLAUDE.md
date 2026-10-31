# pienogiusto-dati

Repo PUBBLICO: pipeline MIMIT -> JSON per provincia su GitHub Pages per l'app PienoGiusto.

## Regole
- Il contratto con l'app e' `docs/CONTRATTO.md` (schema 1). L'app e' gia' sviluppata su quel formato:
  MAI cambiare nomi/tipi/significato delle chiavi senza alzare `schema` e avvisare Cowork/Freebuff.
  Il test `tests/contract/` e' il guardiano: se va cambiato, stai cambiando il contratto.
- Runtime solo libreria standard. `pytest` solo per i test.
- Cancelli FAIL-CLOSED (`pienogiusto_dati/cancelli.py`): nessuna soglia si allenta senza misurarla sui
  dati reali e scriverlo in `docs/DECISIONI.md`.
- Ogni formato nuovo visto dal MIMIT = una fixture in `tests/fixtures/` + un test in `tests/regression/`.
- Nessun commit dei dati su `main`: si pubblicano dal nodo Pi sul branch `gh-pages`
  (`scripts/nodo-pi/pubblica.sh`, docs/DECISIONI.md D13). Il vecchio watchdog/spinta e' messo da parte (D10 sostituita da D13).
- Workflow: `actionlint .github/workflows/*.yml` prima di proporre modifiche.
- Test: `pytest -q`. Rete: `python3 ~/Scrivania/arsenale-ai/scripts/verifica-rete-di-sicurezza.py .`
- git add/commit/push li fa Giuseppe.
- Git: PR senza merge da /lotto-card (arsenale-ai/docs/regole/lotto-card.md): push del ramo e PR li fa `scripts/lotto-card/pubblica-card.sh` dopo i cancelli; il merge (MERGE_AUTO=si) lo fa lo stesso script SOLO a CI verde. L'agente non mergia e non pusha mai su main.

- Leggi `docs/mappa.md` prima di cercare nel codice.

- Il checkout principale è SOLA LETTURA: si lavora nei worktree in ~/Scrivania/_lavoro/ (mai modificare file nel checkout principale).
