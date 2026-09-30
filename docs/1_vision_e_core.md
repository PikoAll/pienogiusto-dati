# Vision e Core
- Nome progetto: pienogiusto-dati (repo dati dell'app PienoGiusto)
- Problema che risolve: l'app non deve scaricare e interpretare i CSV MIMIT (7,5 MB, formato che cambia). Qui si scaricano, si validano e si pubblicano ogni mattina JSON piccoli per provincia.
- Utenti/attori principali: l'app PienoGiusto (legge `index.json` e `p/<SIGLA>.json.gz` da GitHub Pages).
- La funzione che lo distingue: cancelli FAIL-CLOSED: se il dato di oggi e' strano non si pubblica e restano online i dati di ieri.
- Cosa NON è / fuori scope: niente backend, niente storico, niente colonnine elettriche, nessun dato utente.
