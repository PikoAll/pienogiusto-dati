# Fixture

- `anagrafica_reale.csv`, `prezzi_reale.csv`: estratto byte-per-byte dei file MIMIT del 2026-09-29
  (150 impianti di BA + i casi difficili reali: separatore nei campi, virgolette sbilanciate, tab,
  coordinate mancanti, prezzi fuori range) e tutti i loro prezzi.
- Derivate dall'estratto reale (una tantum, 2026-09-30):
  `anagrafica_virgola.csv` / `prezzi_virgola.csv` (formato vecchio con virgola; i prezzi senza riga "Estrazione"),
  `anagrafica_senza_estrazione.csv`, `anagrafica_troncata.csv` / `prezzi_troncato.csv` (tagliati a meta' riga),
  `pagina_errore.html` (pagina d'errore al posto del CSV), `anagrafica_latin1.csv` (cp1252 + CRLF).
- Dati MIMIT, licenza IODL 2.0.
