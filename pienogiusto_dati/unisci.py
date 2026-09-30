"""Join anagrafica and prezzi by idImpianto and group the result by province."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from .parser import RisultatoAnagrafica, RisultatoPrezzi

# Italy bounding box, generous margins: Lampedusa 35.49N, Vetta d'Italia 47.09N,
# Monte Chaberton 6.63E, Otranto 18.52E.
ITALIA_LAT = (35.2, 47.2)
ITALIA_LON = (6.5, 18.6)
# Plausible price range, EUR/L or EUR/kg (methane). Outside = operator typo.
PREZZO_MIN, PREZZO_MAX = 0.3, 4.0
DECIMALI_COORD = 5  # ~1 m


def in_italia(lat: float, lon: float) -> bool:
    return ITALIA_LAT[0] <= lat <= ITALIA_LAT[1] and ITALIA_LON[0] <= lon <= ITALIA_LON[1]


@dataclass
class Unione:
    province: dict[str, list[dict]] = field(default_factory=dict)
    scarti: Counter = field(default_factory=Counter)
    anagrafica: int = 0
    con_coordinate_valide: int = 0
    prezzi_totali: int = 0  # price rows of the published-candidate stations

    @property
    def pubblicati(self) -> int:
        return sum(len(v) for v in self.province.values())

    def bbox(self, sigla: str) -> list[float]:
        pts = self.province[sigla]
        lats = [d["lat"] for d in pts]
        lons = [d["lon"] for d in pts]
        return [min(lats), min(lons), max(lats), max(lons)]


def unisci(anag: RisultatoAnagrafica, prezzi: RisultatoPrezzi) -> Unione:
    u = Unione(anagrafica=len(anag.impianti))
    for id_, lista in prezzi.prezzi.items():
        if id_ not in anag.impianti:
            u.scarti["prezzi_senza_impianto"] += len(lista)
    for id_ in sorted(anag.impianti):
        imp = anag.impianti[id_]
        if imp.lat is None or imp.lon is None or (imp.lat == 0 and imp.lon == 0):
            u.scarti["coordinate_mancanti"] += 1
            continue
        if not in_italia(imp.lat, imp.lon):
            u.scarti["coordinate_fuori_italia"] += 1
            continue
        u.con_coordinate_valide += 1
        lista = prezzi.prezzi.get(id_, [])
        u.prezzi_totali += len(lista)
        buoni = [p for p in lista if PREZZO_MIN <= p.v <= PREZZO_MAX]
        u.scarti["prezzo_fuori_range"] += len(lista) - len(buoni)
        if not buoni:
            u.scarti["senza_prezzi"] += 1
            continue
        buoni.sort(key=lambda p: (p.c, not p.self))
        u.province.setdefault(imp.prov, []).append({
            "id": imp.id, "nome": imp.nome, "band": imp.band, "ind": imp.ind, "com": imp.com,
            "lat": round(imp.lat, DECIMALI_COORD), "lon": round(imp.lon, DECIMALI_COORD),
            "p": [{"c": p.c, "self": p.self, "v": p.v, "t": p.t} for p in buoni],
        })
    u.scarti = Counter({k: v for k, v in u.scarti.items() if v})
    return u
