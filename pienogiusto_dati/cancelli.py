"""FAIL-CLOSED gates: if one fails nothing is published and yesterday's data stays online.

Thresholds calibrated on the real files of 2026-09-29 (docs/RICOGNIZIONE.md):
23,940 stations in anagrafica, 21,681 published, 92,909 price rows,
12 prices out of range (0.013%), 3 stations without coordinates (0.013%).
The header gate lives in the parser (FormatoNonValido).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from .parser import RisultatoAnagrafica, RisultatoPrezzi
from .unisci import Unione, in_italia

# First run / previous index unreachable: absolute floor (-17% vs the 21,681 measured).
MIN_IMPIANTI_ASSOLUTO = 18_000
MAX_VARIAZIONE_IMPIANTI = 0.10
# Single out-of-range prices are discarded; the gate trips when they stop being rare.
MAX_QUOTA_PREZZI_FUORI_RANGE = 0.005
MIN_QUOTA_COORDINATE_VALIDE = 0.95
MAX_QUOTA_RIGHE_MALFORMATE = 0.005
# Rows with U+FFFD after decoding (0 on the real files): above this the encoding is broken.
MAX_QUOTA_RIGHE_SOSTITUITE = 0.001
# prezziDel normally ages ~25 h at publication time; 3 days = MIMIT stuck for 2 days.
MAX_ETA_DATI = timedelta(days=3)

_MALFORMATE = ("riga_malformata", "id_non_valido", "provincia_non_valida", "prezzo_non_valido",
               "self_non_valido", "data_non_valida", "carburante_mancante")


@dataclass(frozen=True)
class Esito:
    nome: str
    ok: bool
    valore: float
    soglia: str

    def come_dict(self) -> dict:
        return {"ok": self.ok, "valore": self.valore, "soglia": self.soglia}


class CancelloFallito(Exception):
    def __init__(self, esiti: list[Esito]):
        self.esiti = esiti
        self.falliti = [e for e in esiti if not e.ok]
        super().__init__("; ".join(f"{e.nome}={e.valore} (soglia {e.soglia})" for e in self.falliti))


def _quota(num: int, den: int) -> float:
    return round(num / den, 6) if den else 1.0


def verifica_cancelli(anag: RisultatoAnagrafica, prezzi: RisultatoPrezzi, unione: Unione,
                      n_precedente: int | None) -> list[Esito]:
    esiti: list[Esito] = []
    n = unione.pubblicati
    if n_precedente:
        variazione = round(abs(n - n_precedente) / n_precedente, 6)
        esiti.append(Esito("impianti", variazione <= MAX_VARIAZIONE_IMPIANTI, variazione,
                           f"<= {MAX_VARIAZIONE_IMPIANTI} rispetto a {n_precedente} (n={n})"))
    else:
        esiti.append(Esito("impianti", n >= MIN_IMPIANTI_ASSOLUTO, n,
                           f">= {MIN_IMPIANTI_ASSOLUTO} (nessun indice precedente)"))

    q = _quota(unione.scarti["prezzo_fuori_range"], unione.prezzi_totali)
    esiti.append(Esito("prezzi_fuori_range", q <= MAX_QUOTA_PREZZI_FUORI_RANGE, q,
                       f"<= {MAX_QUOTA_PREZZI_FUORI_RANGE}"))

    q = _quota(unione.con_coordinate_valide, unione.anagrafica)
    esiti.append(Esito("coordinate_valide", q >= MIN_QUOTA_COORDINATE_VALIDE, q,
                       f">= {MIN_QUOTA_COORDINATE_VALIDE}"))

    fuori = sum(1 for lista in unione.province.values() for d in lista if not in_italia(d["lat"], d["lon"]))
    esiti.append(Esito("coordinate_italia", fuori == 0, fuori, "== 0"))

    for nome, ris in (("righe_anagrafica", anag), ("righe_prezzi", prezzi)):
        q = _quota(sum(ris.scarti[k] for k in _MALFORMATE), ris.righe)
        esiti.append(Esito(nome, q <= MAX_QUOTA_RIGHE_MALFORMATE, q, f"<= {MAX_QUOTA_RIGHE_MALFORMATE}"))

    for nome, ris in (("codifica_anagrafica", anag), ("codifica_prezzi", prezzi)):
        q = _quota(ris.righe_con_sostituzioni, ris.righe)
        esiti.append(Esito(nome, q <= MAX_QUOTA_RIGHE_SOSTITUITE, q, f"<= {MAX_QUOTA_RIGHE_SOSTITUITE}"))

    if any(not e.ok for e in esiti):
        raise CancelloFallito(esiti)
    return esiti


def valuta_novita(prezzi_del_nuovo: str, prezzi_del_pubblicato: str | None, adesso: datetime) -> bool:
    """True = publish. False = nothing new (green). Raises when the online data is stale (red)."""
    if prezzi_del_pubblicato is None:
        return True
    pubblicato = datetime.fromisoformat(prezzi_del_pubblicato)
    if datetime.fromisoformat(prezzi_del_nuovo) > pubblicato:
        return True
    eta = adesso - pubblicato
    if eta > MAX_ETA_DATI:
        ore = round(eta.total_seconds() / 3600, 1)
        raise CancelloFallito([Esito("dati_fermi", False, ore,
                                     f"<= {MAX_ETA_DATI.total_seconds() / 3600:.0f} h dal prezziDel pubblicato")])
    return False

