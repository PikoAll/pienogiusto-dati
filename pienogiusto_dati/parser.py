"""Tolerant parser for the two MIMIT CSV files.

What the real files look like (see docs/RICOGNIZIONE.md):
- optional first line "Estrazione del YYYY-MM-DD" before the header;
- separator "|" since 2026-02-10 (comma or semicolon before);
- NO quoting: stray, unbalanced double quotes are just characters, so the csv
  module must not interpret them (it would merge lines);
- the separator can appear unescaped inside text fields: rows with extra fields
  are recovered by anchoring the fixed columns at both ends.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime

INTESTAZIONI_ANAGRAFICA = [
    "idImpianto", "Gestore", "Bandiera", "Tipo Impianto", "Nome Impianto",
    "Indirizzo", "Comune", "Provincia", "Latitudine", "Longitudine",
]
INTESTAZIONI_PREZZI = ["idImpianto", "descCarburante", "prezzo", "isSelf", "dtComu"]

SEPARATORI = ("|", ";", ",")
TIPI_IMPIANTO = {"Stradale", "Autostradale"}
# Junk fragment that some operators' software appends after an unescaped separator.
FRAMMENTI_SPAZZATURA = {"gestori.prezzibenzina.it"}
FORMATI_DATA = ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S")

_RE_ESTRAZIONE = re.compile(r"^Estrazione del\s+(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})", re.I)
_RE_PROVINCIA = re.compile(r"^[A-Z]{2}$")
_RE_SPAZI = re.compile(r"\s+")


class FormatoNonValido(Exception):
    """The file is not the CSV we expect (HTML page, empty, different header)."""


@dataclass(frozen=True)
class Impianto:
    id: int
    nome: str
    band: str
    ind: str
    com: str
    prov: str
    lat: float | None
    lon: float | None


@dataclass(frozen=True)
class Prezzo:
    c: str
    self: bool
    v: float
    t: str  # ISO 8601, local time in Rome, no offset (as in the contract)


@dataclass
class Tabella:
    estrazione: date | None
    separatore: str
    codifica: str
    righe: list[list[str]]
    righe_con_sostituzioni: int = 0  # rows containing U+FFFD after decoding


@dataclass
class RisultatoAnagrafica:
    estrazione: date | None
    separatore: str
    codifica: str
    righe: int
    impianti: dict[int, Impianto] = field(default_factory=dict)
    scarti: Counter = field(default_factory=Counter)
    righe_con_sostituzioni: int = 0


@dataclass
class RisultatoPrezzi:
    estrazione: date | None
    separatore: str
    codifica: str
    righe: int
    prezzi: dict[int, list[Prezzo]] = field(default_factory=dict)
    scarti: Counter = field(default_factory=Counter)
    ultima_comunicazione: datetime | None = None
    righe_con_sostituzioni: int = 0


def decodifica(dati: bytes) -> tuple[str, str]:
    try:
        return dati.decode("utf-8-sig"), "utf-8"
    except UnicodeDecodeError:
        return dati.decode("cp1252", errors="replace"), "cp1252"


def _pulisci(valore: str) -> str:
    return _RE_SPAZI.sub(" ", valore).strip().strip('"').strip()


def _leggi_data_estrazione(testo: str) -> date | None:
    m = _RE_ESTRAZIONE.match(testo.strip())
    if not m:
        return None
    raw = m.group(1)
    fmt = "%Y-%m-%d" if "-" in raw else "%d/%m/%Y"
    return datetime.strptime(raw, fmt).date()


def leggi_tabella(dati: bytes, intestazioni: list[str]) -> Tabella:
    testo, codifica = decodifica(dati)
    inizio = testo.lstrip()[:1024].lower()
    if inizio.startswith("<") or "<html" in inizio:
        raise FormatoNonValido("il file e' una pagina HTML, non un CSV")
    linee = [l for l in testo.splitlines() if l.strip()]
    if not linee:
        raise FormatoNonValido("file vuoto")
    estrazione = None
    if _RE_ESTRAZIONE.match(linee[0].strip()):
        estrazione = _leggi_data_estrazione(linee[0])
        linee = linee[1:]
    if not linee:
        raise FormatoNonValido("intestazioni assenti")
    testa = linee[0]
    for sep in SEPARATORI:
        if [c.strip() for c in testa.split(sep)] == intestazioni:
            righe = [l.split(sep) for l in linee[1:]]
            sostituite = sum(1 for l in linee[1:] if "\ufffd" in l)
            return Tabella(estrazione, sep, codifica, righe, sostituite)
    raise FormatoNonValido(f"intestazioni inattese: {testa[:200]!r}")


def _numero(valore: str) -> float | None:
    try:
        return float(valore.strip().replace(",", "."))
    except ValueError:
        return None


def _unisci_testo(parti: list[str]) -> str:
    buone = [p for p in (_pulisci(x) for x in parti) if p and p not in FRAMMENTI_SPAZZATURA]
    return " ".join(buone)


def _campi_anagrafica(f: list[str]) -> list[str] | None:
    """Map a raw row to the 10 columns, recovering unescaped separators."""
    if len(f) == 10:
        return f
    if len(f) < 10:
        return None
    centro = f[1:-4]  # gestore.., bandiera, tipo, nome.., indirizzo
    k = next((i for i in range(1, len(centro) - 1) if _pulisci(centro[i]) in TIPI_IMPIANTO), None)
    if k is None:
        return None
    gestore = _unisci_testo(centro[: k - 1])
    nome = _unisci_testo(centro[k + 1 : -1])
    return [f[0], gestore, centro[k - 1], centro[k], nome, centro[-1], *f[-4:]]


def parse_anagrafica(dati: bytes) -> RisultatoAnagrafica:
    tab = leggi_tabella(dati, INTESTAZIONI_ANAGRAFICA)
    ris = RisultatoAnagrafica(tab.estrazione, tab.separatore, tab.codifica, len(tab.righe),
                              righe_con_sostituzioni=tab.righe_con_sostituzioni)
    for grezza in tab.righe:
        f = _campi_anagrafica(grezza)
        if f is None:
            ris.scarti["riga_malformata"] += 1
            continue
        f = [_pulisci(x) for x in f]
        if not f[0].isdigit():
            ris.scarti["id_non_valido"] += 1
            continue
        if not _RE_PROVINCIA.match(f[7]):
            ris.scarti["provincia_non_valida"] += 1
            continue
        id_ = int(f[0])
        if id_ in ris.impianti:
            ris.scarti["id_duplicato"] += 1
            continue
        ris.impianti[id_] = Impianto(
            id=id_, nome=f[4], band=f[2], ind=f[5], com=f[6], prov=f[7],
            lat=_numero(f[8]) if f[8] else None, lon=_numero(f[9]) if f[9] else None,
        )
    return ris


def _leggi_dt(valore: str) -> datetime | None:
    for fmt in FORMATI_DATA:
        try:
            return datetime.strptime(valore.strip(), fmt)
        except ValueError:
            pass
    return None


def parse_prezzi(dati: bytes) -> RisultatoPrezzi:
    tab = leggi_tabella(dati, INTESTAZIONI_PREZZI)
    ris = RisultatoPrezzi(tab.estrazione, tab.separatore, tab.codifica, len(tab.righe),
                          righe_con_sostituzioni=tab.righe_con_sostituzioni)
    per_chiave: dict[tuple[int, str, bool], tuple[datetime, Prezzo]] = {}
    for f in tab.righe:
        if len(f) < 5:
            ris.scarti["riga_malformata"] += 1
            continue
        if len(f) > 5:  # separator inside the fuel name
            f = [f[0], tab.separatore.join(f[1:-3]), *f[-3:]]
        f = [_pulisci(x) for x in f]
        if not f[0].isdigit():
            ris.scarti["id_non_valido"] += 1
            continue
        v = _numero(f[2])
        if v is None:
            ris.scarti["prezzo_non_valido"] += 1
            continue
        if f[3] not in ("0", "1"):
            ris.scarti["self_non_valido"] += 1
            continue
        dt = _leggi_dt(f[4])
        if dt is None:
            ris.scarti["data_non_valida"] += 1
            continue
        if not f[1]:
            ris.scarti["carburante_mancante"] += 1
            continue
        p = Prezzo(c=f[1], self=f[3] == "1", v=v, t=dt.isoformat(timespec="seconds"))
        chiave = (int(f[0]), p.c, p.self)
        if chiave in per_chiave:
            ris.scarti["prezzo_duplicato"] += 1
            if per_chiave[chiave][0] >= dt:
                continue
        per_chiave[chiave] = (dt, p)
        if ris.ultima_comunicazione is None or dt > ris.ultima_comunicazione:
            ris.ultima_comunicazione = dt
    for (id_, _, _), (_, p) in per_chiave.items():
        ris.prezzi.setdefault(id_, []).append(p)
    return ris
