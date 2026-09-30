# Architettura e Stack
- Python 3.12, solo libreria standard a runtime (urllib, csv-free parsing, json, gzip, zoneinfo). `pytest` solo per i test.
- GitHub Actions (`pubblica.yml`) -> artefatto -> GitHub Pages. Nessun commit dei dati.
- Contratto con l'app: `docs/CONTRATTO.md` (schema 1). Fonte di verità per l'app Flutter.

## Pipeline
`scarica.py` (3 tentativi, UA, no HTML, no troncati) -> `parser.py` (tollerante) -> `unisci.py` (join per id, filtri, province) -> `cancelli.py` (FAIL-CLOSED) -> `pubblica.py` (scrive in `site.in-corso/` poi rinomina in `site/`).

## Struttura cartelle
- `pienogiusto_dati/` codice · `tests/{unit,regression,integration,smoke,contract}` · `tests/fixtures/` estratto reale 2026-09-29 · `docs/`.

## Convenzioni
- Commit: tipo(scope): descrizione
- Exit code: 0 pubblicato, 1 cancello fallito, 2 download/uso.
