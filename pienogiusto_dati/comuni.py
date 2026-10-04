"""National list of municipalities (comuni.json.gz), derived from the published stations.

Why: in the app, when the GPS is unavailable, the user searches a municipality by name. The list
cannot come from the per-province files (downloading one needs a position): without this file the
first start without GPS is a dead end (measured on the emulator, 2026-10-04).

One entry per (name, province): the same name in two provinces gives two entries.
    {"n": "MONOPOLI", "p": "BA", "lat": 40.95, "lon": 17.30, "k": 27}
`lat`/`lon` = mean of the coordinates of the published stations of that municipality, `k` = their number.
"""
from __future__ import annotations

import re

from .unisci import DECIMALI_COORD, Unione

_RE_SPAZI = re.compile(r"\s+")


def normalizza_nome(nome: str) -> str:
    """Trim and collapse whitespace; case is kept as in the source data."""
    return _RE_SPAZI.sub(" ", nome).strip()


def media(valori: list[float]) -> float:
    return round(sum(valori) / len(valori), DECIMALI_COORD)


def elenco_comuni(unione: Unione) -> list[dict]:
    """Sorted by name, then province. An empty name is NOT dropped: the gate `comuni_nome_vuoto` must see it."""
    gruppi: dict[tuple[str, str], list[dict]] = {}
    for sigla, impianti in unione.province.items():
        for d in impianti:
            gruppi.setdefault((normalizza_nome(d["com"]), sigla), []).append(d)
    return [
        {"n": n, "p": p, "lat": media([d["lat"] for d in pts]), "lon": media([d["lon"] for d in pts]),
         "k": len(pts)}
        for (n, p), pts in sorted(gruppi.items())
    ]
