"""Robust download of the MIMIT files and of the previously published index."""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

URL_ANAGRAFICA = "https://www.mimit.gov.it/images/exportCSV/anagrafica_impianti_attivi.csv"
URL_PREZZI = "https://www.mimit.gov.it/images/exportCSV/prezzo_alle_8.csv"
USER_AGENT = "PienoGiusto-dati/1.0 (+https://github.com/PikoAll/pienogiusto-dati; open data IODL 2.0)"
TIMEOUT_S = 60
TENTATIVI = 3
ATTESA_BASE_S = 5  # waits 5 s, then 15 s


class ErroreDownload(Exception):
    pass


def _una_volta(url: str, apri, timeout: int) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with apri(req, timeout=timeout) as r:
        tipo = r.headers.get("Content-Type", "") or ""
        atteso = r.headers.get("Content-Length")
        corpo = r.read()
    if "html" in tipo.lower() or corpo.lstrip()[:1] == b"<":
        raise ErroreDownload(f"{url}: risposta HTML invece del CSV (Content-Type {tipo!r})")
    if atteso is not None and int(atteso) != len(corpo):
        raise ErroreDownload(f"{url}: risposta troncata ({len(corpo)} di {atteso} byte)")
    if not corpo:
        raise ErroreDownload(f"{url}: risposta vuota")
    return corpo


def scarica(url: str, *, apri=urllib.request.urlopen, dormi=time.sleep,
            tentativi: int = TENTATIVI, timeout: int = TIMEOUT_S) -> bytes:
    ultimo: Exception | None = None
    for i in range(tentativi):
        if i:
            dormi(ATTESA_BASE_S * 3 ** (i - 1))
        try:
            return _una_volta(url, apri, timeout)
        except (ErroreDownload, urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            ultimo = e
            print(f"download {url} tentativo {i + 1}/{tentativi} fallito: {e}", file=sys.stderr)
    raise ErroreDownload(f"{url}: {tentativi} tentativi falliti, ultimo errore: {ultimo}")


@dataclass(frozen=True)
class IndicePrecedente:
    n: int  # total stations
    prezzi_del: str | None


def indice_precedente(url: str | None, *, apri=urllib.request.urlopen,
                      timeout: int = 30) -> IndicePrecedente | None:
    """What the currently published index.json says; None if unknown."""
    if not url:
        return None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with apri(req, timeout=timeout) as r:
            dati = json.loads(r.read())
        return IndicePrecedente(sum(int(p["n"]) for p in dati["province"]), dati.get("prezziDel"))
    except (urllib.error.URLError, OSError, ValueError, KeyError, TypeError) as e:
        print(f"indice precedente non disponibile ({url}): {e}", file=sys.stderr)
        return None
