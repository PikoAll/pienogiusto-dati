# Contratto app <-> dati — schema 1

Copia vincolante di `freebuff/PienoGiusto/doc/03_dati-e-architettura.md` (sezione "Formato", 2026-09-30),
con le precisazioni di come lo scrive la pipeline. Guardiano: `tests/contract/test_contratto.py`.

## `index.json`
```json
{ "schema": 1, "pubblicato": "2026-09-30T07:10:00Z", "prezziDel": "2026-09-29T08:00:00+02:00",
  "province": [ { "sigla": "BA", "file": "p/BA.json.gz", "n": 412, "bbox": [40.73, 16.07, 41.33, 17.49] } ],
  "comuni": "comuni.json.gz" }
```
La chiave `comuni` e' stata **aggiunta il 2026-10-04** (campo in piu', `schema` resta 1: l'app che non la
conosce la ignora). Punta al file dell'elenco nazionale dei comuni qui sotto.

## `comuni.json.gz` — elenco nazionale dei comuni (dal 2026-10-04)
Serve alla ricerca per comune quando il GPS non risponde: l'app lo scarica una volta, senza bisogno di una
posizione, e da li' risale alla provincia da caricare.
```json
{ "schema": 1, "comuni": [ { "n": "MONOPOLI", "p": "BA", "lat": 40.95, "lon": 17.30, "k": 27 } ] }
```
| Chiave | Regola |
|---|---|
| `n` | campo `Comune` dell'anagrafica normalizzato: spazi ai bordi tolti, spazi multipli/tab -> uno spazio, maiuscole/minuscole come nel dato; mai vuoto |
| `p` | sigla della provincia (2 lettere maiuscole), sempre presente in `province` di `index.json` |
| `lat`,`lon` | media delle coordinate degli impianti pubblicati di quel comune, 5 decimali; sempre dentro il `bbox` della provincia |
| `k` | numero di impianti pubblicati di quel comune (>= 1); la somma dei `k` di una provincia = il suo `n` |
| ordine | per `n`, poi `p`; uno stesso nome in due province = due voci distinte |
| file | gzip, JSON compatto UTF-8 (~87 KB gz, ~5.300 comuni il 2026-10-03) |

## `p/BA.json.gz`
```json
{ "schema": 1, "impianti": [
  { "id": 12345, "nome": "…", "band": "Q8", "ind": "Via …", "com": "MONOPOLI", "lat": 40.95, "lon": 17.30,
    "p": [ { "c": "Gasolio", "self": true, "v": 1.679, "t": "2026-09-28T19:12:00" } ] } ] }
```

## Precisazioni (come le scrive la pipeline)
| Chiave | Regola |
|---|---|
| `pubblicato` | UTC, formato `AAAA-MM-GGThh:mm:ssZ`, momento del build |
| `prezziDel` | ore 08:00 ora di Roma (con offset +01/+02) del giorno della riga "Estrazione del" del file prezzi; se manca, giorno dell'ultima `dtComu` |
| `province` | ordinate per sigla; sigla = 2 lettere maiuscole (107 al 2026-09-29, incluso `SU`) |
| `n` | = numero di elementi di `impianti` nel file |
| `bbox` | `[latMin, lonMin, latMax, lonMax]`, calcolato sui punti pubblicati |
| `impianti` | ordinati per `id`; solo impianti con coordinate valide in Italia e almeno un prezzo valido |
| `lat`,`lon` | float arrotondati a 5 decimali (~1 m) |
| `nome`,`band`,`ind`,`com` | stringhe ripulite (spazi multipli/tab -> uno spazio, virgolette ai bordi tolte); `nome` puo' essere vuoto |
| `p` | mai vuoto; ordinato per `c` poi self prima del servito; una sola voce per (`c`,`self`), la piu' recente |
| `c` | `descCarburante` originale (60 valori distinti il 2026-09-29): la mappatura in famiglie sta nell'app |
| `v` | float, sempre fra 0,3 e 4,0 (fuori range = scartato) |
| `t` | `dtComu` in ISO 8601 **ora locale di Roma, senza offset**, come nell'esempio |
| file | gzip, JSON compatto UTF-8 |

Qualsiasi modifica incompatibile (chiave rinominata/tolta, tipo cambiato) richiede `schema: 2`.
Aggiungere chiavi nuove e' compatibile solo se l'app le ignora: da concordare prima con Cowork.
