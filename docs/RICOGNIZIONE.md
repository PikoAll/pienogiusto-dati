# Ricognizione dei dati reali — 2026-09-30

Scaricati una volta alle 12:42 del 2026-09-30 da `https://www.mimit.gov.it/images/exportCSV/` (URL invariati).

| | `anagrafica_impianti_attivi.csv` | `prezzo_alle_8.csv` |
|---|---|---|
| Peso | 3.576.735 byte (3,4 MB) | 3.945.433 byte (3,8 MB) |
| Righe dati | 23.940 | 92.909 |
| Codifica | UTF-8 (senza BOM) | ASCII (quindi UTF-8) |
| Separatore | `\|` | `\|` |
| Prima riga | `Estrazione del 2026-09-29` poi intestazioni | idem |
| Fine file | con a capo | **senza** a capo finale |
| Content-Type | `text/csv`, `Content-Length` presente | idem |
| Last-Modified | — | `Wed, 30 Sep 2026 06:45:07 GMT` (= 08:45 a Roma) |

## Trappole trovate (tutte coperte da test)
1. **Nessun quoting, virgolette sbilanciate**: 1.200 righe contengono `"`, alcune non chiuse
   (`46593|"MEGA SERVICE S.A.S. …|Q8|…`). Il modulo `csv` di Python con le impostazioni di default
   **fonde le righe** (ne perdeva ~33 e faceva apparire 33 "prezzi senza impianto" inesistenti).
   Il parser divide a mano sul separatore.
2. **Separatore dentro i campi**: 112 righe a 11 campi e 1 a 12 (23.827 regolari a 10) (es. `STOIL SIMPLE | gestori.prezzibenzina.it`,
   anche nel Gestore). Recupero: colonne fisse ancorate ai due lati, `Tipo Impianto` (Stradale/Autostradale)
   come ancora centrale, frammento `gestori.prezzibenzina.it` scartato. Dopo il recupero: 0 righe malformate.
3. **Tab dentro i nomi** (22 righe, es. `19834\tMONTALLEGRO`): normalizzati a spazio.
4. **Prezzi assurdi**: 12 righe fuori 0,3–4,0 (0,100 · 0,113 · 4,999 · 8,888), su 6 impianti.
5. **Prezzi vecchissimi**: `dtComu` va dal 2013-05-23 al 2026-09-29 08:03; 154 righe precedenti al 2026.
   Si pubblicano (l'app le colora di rosso per eta').

## Valori
- `descCarburante`: 60 valori distinti. I principali: Benzina 34.162 · Gasolio 34.140 · Blue Diesel 5.687 ·
  GPL 4.700 · HVOlution 2.432 · Supreme Diesel 1.590 · Metano 1.577 · Blue Super 1.456 · HVO 1.402 ·
  Hi-Q Diesel 1.358 · … · GNL 190 · L-GNC 130 · coda lunga di nomi commerciali (es. `Gasolio Artico` e
  `Gasolio artico`, `HVOlution` e `HVOvolution`). Mappatura in famiglie: lato app.
- `isSelf`: 51.230 self (`1`), 41.679 servito (`0`).
- `dtComu`: `GG/MM/AAAA hh:mm:ss`, ora locale.
- `Tipo Impianto`: Stradale 23.398 · Autostradale 542.
- Province: 107 sigle (incluso `SU` Sud Sardegna), nessuna vuota. Max RM 1.526, min TS 38.

## Coordinate
- 3 impianti senza coordinate (campi vuoti: 60502 BN, 60116 FR, 57660 RE).
- 0 impianti fuori dal riquadro Italia (lat 35,2–47,2 · lon 6,5–18,6).

## Unione
- Impianti con prezzi e coordinate valide: **21.681** su 23.940 (2.256 senza prezzi, 3 senza coordinate).
- Prezzi senza impianto in anagrafica: 0. Duplicati (id, carburante, self): 0.

## Soglie tarate su questi numeri (`pienogiusto_dati/cancelli.py`)
| Cancello | Misurato | Soglia |
|---|---|---|
| impianti, primo giro | 21.681 | >= 18.000 (-17%) |
| impianti, giorni successivi | — | ±10% rispetto all'`index.json` pubblicato |
| prezzi fuori range | 0,013% | <= 0,5% (le singole righe fuori range si scartano) |
| coordinate valide | 99,99% | >= 95% |
| coordinate fuori Italia fra i pubblicati | 0 | == 0 |
| righe malformate (per file) | 0% | <= 0,5% |
| intestazioni | esatte | esatte (dopo `strip`), altrimenti rifiuto |
| codifica: righe con `�` (per file, giro 2) | 0 | <= 0,1% |
| dati fermi (giro 2) | eta' ~25 h al run | `prezziDel` uguale: non si ripubblica; rosso se il pubblicato ha > 3 giorni |

## Output (prova end-to-end, dati veri, 2026-09-30)
- 107 file provincia, **1.520.512 byte** gzip in totale (`site/` 1,7 MB con index e report).
- `index.json` 9,6 KB. `BA.json.gz` **25.197 byte** (162 KB non compresso, 376 impianti). Il piu' grande: RM 88 KB.
- Tempo: 4,7 s compreso il download; memoria massima 135 MB.
