"""Data-driven thresholds for the gates (PGD-7): archive the published days, compute and load soglie.json.

    python3 -m pienogiusto_dati.soglie archivia --base-url URL --archivio DIR
    python3 -m pienogiusto_dati.soglie calcola --archivio DIR --uscita config/soglie.json

`archivia` keeps one folder per day (AAAA-MM-GG, the day of prezziDel) with index.json and p/*.json.gz; it never
deletes old days. `calcola` reads the last 30 days and writes soglie.json (nothing with fewer than 7 days).
`carica` is used by pubblica.py: it returns None (constants stay in charge) when the file is not trustworthy.
Exit codes: 0 done (or nothing to do), 2 download/IO/usage error. Standard library only.
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import statistics
import sys
import zlib
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .scarica import ErroreDownload, scarica
from .unisci import PREZZO_MAX, PREZZO_MIN

FINESTRA_GIORNI = 30
MIN_GIORNI = 7
MAX_ETA_SOGLIE = timedelta(days=45)
MIN_PREZZI_CARBURANTE = 100
MARGINE = 0.10
QUOTA_IMPIANTI_MIN = 0.8


def _log(msg: str) -> None:
    print(msg, file=sys.stderr)


# --------------------------------------------------------------------------- archivia

def _percorso_sicuro(rel: str) -> bool:
    p = Path(rel)
    return bool(rel) and not p.is_absolute() and ".." not in p.parts


def archivia(base_url: str, archivio: Path) -> int:
    base = base_url.rstrip("/")
    try:
        grezzo = scarica(f"{base}/index.json", tentativi=1 if base.startswith("file:") else 3)
        indice = json.loads(grezzo)
        giorno = str(indice["prezziDel"])[:10]
        date.fromisoformat(giorno)
        file_province = [p["file"] for p in indice["province"]]
        if not all(_percorso_sicuro(f) for f in file_province):
            raise ValueError("percorso di provincia non valido nell'indice")
        if (archivio / giorno).is_dir():
            print(f"archivio: giorno {giorno} gia' presente, niente da fare")
            return 0
        archivio.mkdir(parents=True, exist_ok=True)
        # fixed name per day: a failed run is reused by the next one, leftovers don't pile up
        temp = archivio / f".in-corso-{giorno}"
        (temp / "p").mkdir(parents=True, exist_ok=True)
        (temp / "index.json").write_bytes(grezzo)
        for rel in file_province:
            dati = scarica(f"{base}/{rel}", tentativi=1 if base.startswith("file:") else 3)
            (temp / rel).write_bytes(dati)
        os.rename(temp, archivio / giorno)
    except (ErroreDownload, OSError, ValueError, KeyError, TypeError) as e:
        _log(f"ERRORE archivio: {e}")
        return 2
    print(f"archivio: salvato il giorno {giorno} in {archivio / giorno}")
    return 0


# --------------------------------------------------------------------------- calcola

def _giorni_in_finestra(archivio: Path, oggi: date) -> list[Path]:
    primo = oggi - timedelta(days=FINESTRA_GIORNI - 1)
    trovati = []
    for d in sorted(archivio.iterdir()) if archivio.is_dir() else []:
        try:
            g = date.fromisoformat(d.name)
        except ValueError:
            continue
        if primo <= g <= oggi and (d / "index.json").is_file():
            trovati.append(d)
    return trovati


def _leggi_giorno(cartella: Path) -> tuple[dict[str, int], dict[str, list[float]]]:
    indice = json.loads((cartella / "index.json").read_text(encoding="utf-8"))
    n_province: dict[str, int] = {}
    prezzi: dict[str, list[float]] = {}
    for p in indice["province"]:
        n_province[p["sigla"]] = int(p["n"])
        dati = json.loads(gzip.decompress((cartella / p["file"]).read_bytes()))
        for impianto in dati["impianti"]:
            for x in impianto["p"]:
                prezzi.setdefault(x["c"], []).append(float(x["v"]))
    return n_province, prezzi


def calcola(archivio: Path, uscita: Path, adesso: datetime | None = None) -> int:
    oggi = adesso.date() if adesso else date.today()  # archive days are named in local dates
    adesso = adesso or datetime.now(timezone.utc)
    prezzi: dict[str, list[float]] = {}
    per_provincia: dict[str, list[int]] = {}
    giorni = 0
    for cartella in _giorni_in_finestra(archivio, oggi):
        try:
            n_province, prezzi_giorno = _leggi_giorno(cartella)
        except (OSError, ValueError, KeyError, TypeError, EOFError, zlib.error) as e:
            _log(f"calcola: giorno {cartella.name} saltato, illeggibile: {e}")
            continue
        giorni += 1
        for sigla, n in n_province.items():
            per_provincia.setdefault(sigla, []).append(n)
        for c, valori in prezzi_giorno.items():
            prezzi.setdefault(c, []).extend(valori)
    if giorni < MIN_GIORNI:
        _log(f"calcola: solo {giorni} giorni nell'archivio (servono almeno {MIN_GIORNI}): soglie.json non creato")
        return 0

    soglie_prezzi = {}
    for c, valori in sorted(prezzi.items()):
        if len(valori) < MIN_PREZZI_CARBURANTE:
            _log(f"calcola: {c} escluso, solo {len(valori)} prezzi (servono {MIN_PREZZI_CARBURANTE})")
            continue
        q = statistics.quantiles(valori, n=100, method="inclusive")
        soglie_prezzi[c] = {"min": round(max(PREZZO_MIN, q[0] * (1 - MARGINE)), 4),
                            "max": round(min(PREZZO_MAX, q[98] * (1 + MARGINE)), 4)}
    risultato = {
        "calcolato_il": adesso.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "giorni": giorni,
        "prezzi": soglie_prezzi,
        "impianti_min": {s: round(statistics.median(v) * QUOTA_IMPIANTI_MIN, 2)
                         for s, v in sorted(per_provincia.items())},
    }
    try:
        uscita.parent.mkdir(parents=True, exist_ok=True)
        temp = uscita.with_name(uscita.name + ".in-corso")
        temp.write_text(json.dumps(risultato, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(temp, uscita)
    except OSError as e:
        _log(f"ERRORE scrittura {uscita}: {e}")
        return 2
    print(f"calcola: {uscita} creato con {giorni} giorni, {len(soglie_prezzi)} carburanti")
    return 0


# --------------------------------------------------------------------------- carica

def carica(percorso: Path | str, adesso: datetime) -> dict | None:
    """The thresholds, or None (and the reason on stderr) when the constants must be used."""
    percorso = Path(percorso)
    try:
        dati = json.loads(percorso.read_text(encoding="utf-8"))
        giorni = dati["giorni"]
        calcolato = datetime.fromisoformat(str(dati["calcolato_il"]).replace("Z", "+00:00"))
        if not isinstance(dati["prezzi"], dict) or not isinstance(dati["impianti_min"], dict):
            raise ValueError("prezzi/impianti_min non sono oggetti")
        for c, s in dati["prezzi"].items():
            float(s["min"]), float(s["max"])
        for v in dati["impianti_min"].values():
            float(v)
        if isinstance(giorni, bool) or not isinstance(giorni, int):
            raise ValueError("giorni non e' un intero")
    except FileNotFoundError:
        _log(f"soglie: {percorso} manca, uso le costanti")
        return None
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
        _log(f"soglie: {percorso} illeggibile ({e}), uso le costanti")
        return None
    if giorni < MIN_GIORNI:
        _log(f"soglie: {percorso} calcolato su {giorni} giorni (< {MIN_GIORNI}), uso le costanti")
        return None
    if calcolato.tzinfo is None:
        calcolato = calcolato.replace(tzinfo=timezone.utc)
    if adesso.tzinfo is None:
        adesso = adesso.replace(tzinfo=timezone.utc)
    if adesso - calcolato > MAX_ETA_SOGLIE:
        _log(f"soglie: {percorso} calcolato il {calcolato.date()}, piu' vecchio di 45 giorni, uso le costanti")
        return None
    return dati


# --------------------------------------------------------------------------- CLI

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="pienogiusto_dati.soglie", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="comando", required=True)
    a1 = sub.add_parser("archivia", help="save the published day in the archive")
    a1.add_argument("--base-url", required=True, help="URL of the published site (without index.json)")
    a1.add_argument("--archivio", required=True, type=Path)
    a2 = sub.add_parser("calcola", help="compute soglie.json from the archive")
    a2.add_argument("--archivio", required=True, type=Path)
    a2.add_argument("--uscita", required=True, type=Path)
    a = ap.parse_args(argv)
    if a.comando == "archivia":
        return archivia(a.base_url, a.archivio)
    return calcola(a.archivio, a.uscita)


if __name__ == "__main__":
    sys.exit(main())
