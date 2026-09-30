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
- Nessun commit dei dati: si pubblicano come artefatto Pages. Nessun commit automatico di keepalive:
  lo spegnimento per inattivita' lo gestisce `scripts/watchdog.sh` (timer utente, docs/DECISIONI.md D10).
- Workflow: `actionlint .github/workflows/*.yml` prima di proporre modifiche.
- Test: `pytest -q`. Rete: `python3 ~/Scrivania/arsenale-ai/scripts/verifica-rete-di-sicurezza.py .`
- git add/commit/push li fa Giuseppe.
