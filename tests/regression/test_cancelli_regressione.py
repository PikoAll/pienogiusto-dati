"""Regression tests for the FAIL-CLOSED gates.

Each gate has a red case (publication must be refused) and a green case, with
thresholds calibrated on the real files of 2026-09-29 (docs/RICOGNIZIONE.md).
"""
from collections import Counter
from datetime import datetime, timedelta, timezone

import pytest

from pienogiusto_dati.cancelli import (
    MIN_COMUNI,
    MIN_IMPIANTI_ASSOLUTO,
    CancelloFallito,
    MAX_ETA_DATI,
    valuta_novita,
    verifica_cancelli,
)
from pienogiusto_dati.parser import RisultatoAnagrafica, RisultatoPrezzi
from pienogiusto_dati.unisci import Unione


def stato(pubblicati=21_000, anagrafica=23_900, coord=23_897, prezzi_tot=92_000, fuori_range=12,
          malformate_a=0, malformate_p=0, fuori_italia=False, sostituite_a=0, sostituite_p=0):
    a = RisultatoAnagrafica(None, "|", "utf-8", anagrafica, {}, Counter(riga_malformata=malformate_a),
                            righe_con_sostituzioni=sostituite_a)
    p = RisultatoPrezzi(None, "|", "utf-8", 92_909, {}, Counter(riga_malformata=malformate_p),
                        righe_con_sostituzioni=sostituite_p)
    punto = {"lat": 17.3 if fuori_italia else 40.9, "lon": 40.9 if fuori_italia else 17.3}
    u = Unione(province={"BA": [punto] * pubblicati}, scarti=Counter(prezzo_fuori_range=fuori_range),
               anagrafica=anagrafica, con_coordinate_valide=coord, prezzi_totali=prezzi_tot)
    return a, p, u


def nomi_falliti(exc_info):
    return {e.nome for e in exc_info.value.falliti}


def test_giornata_reale_passa():
    esiti = verifica_cancelli(*stato(), comuni(), n_precedente=21_200)
    assert all(e.ok for e in esiti)
    assert {e.nome for e in esiti} == {"impianti", "prezzi_fuori_range", "coordinate_valide",
                                       "coordinate_italia", "righe_anagrafica", "righe_prezzi",
                                       "codifica_anagrafica", "codifica_prezzi",
                                       "comuni", "comuni_bbox", "comuni_nome_vuoto"}


@pytest.mark.parametrize("n", [18_000, 25_000])
def test_impianti_oltre_10_per_cento_dal_precedente_rosso(n):
    with pytest.raises(CancelloFallito) as e:
        verifica_cancelli(*stato(pubblicati=n), comuni(), n_precedente=21_000)
    assert nomi_falliti(e) == {"impianti"}


@pytest.mark.parametrize("n", [18_900, 23_100])
def test_impianti_entro_10_per_cento_verde(n):
    verifica_cancelli(*stato(pubblicati=n), comuni(), n_precedente=21_000)


def test_primo_giro_sotto_la_soglia_assoluta_rosso():
    with pytest.raises(CancelloFallito) as e:
        verifica_cancelli(*stato(pubblicati=MIN_IMPIANTI_ASSOLUTO - 1), comuni(), n_precedente=None)
    assert nomi_falliti(e) == {"impianti"}


def test_primo_giro_sopra_la_soglia_assoluta_verde():
    verifica_cancelli(*stato(pubblicati=MIN_IMPIANTI_ASSOLUTO), comuni(), n_precedente=None)


def test_troppi_prezzi_fuori_range_rosso():
    with pytest.raises(CancelloFallito) as e:
        verifica_cancelli(*stato(fuori_range=500), comuni(), n_precedente=None)
    assert nomi_falliti(e) == {"prezzi_fuori_range"}


def test_pochi_prezzi_fuori_range_verde():
    verifica_cancelli(*stato(fuori_range=400), comuni(), n_precedente=None)


def test_meno_del_95_per_cento_con_coordinate_rosso():
    with pytest.raises(CancelloFallito) as e:
        verifica_cancelli(*stato(anagrafica=23_900, coord=22_600), comuni(), n_precedente=None)
    assert nomi_falliti(e) == {"coordinate_valide"}


def test_impianto_pubblicato_fuori_italia_rosso():
    with pytest.raises(CancelloFallito) as e:
        # municipalities follow the (swapped) stations: only the Italy gate must trip
        verifica_cancelli(*stato(fuori_italia=True), comuni(lat=17.3, lon=40.9), n_precedente=None)
    assert nomi_falliti(e) == {"coordinate_italia"}


def test_troppe_righe_malformate_anagrafica_rosso():
    with pytest.raises(CancelloFallito) as e:
        verifica_cancelli(*stato(malformate_a=200), comuni(), n_precedente=None)
    assert nomi_falliti(e) == {"righe_anagrafica"}


def test_troppe_righe_malformate_prezzi_rosso():
    with pytest.raises(CancelloFallito) as e:
        verifica_cancelli(*stato(malformate_p=1_000), comuni(), n_precedente=None)
    assert nomi_falliti(e) == {"righe_prezzi"}


def test_piu_cancelli_falliti_riportati_tutti():
    with pytest.raises(CancelloFallito) as e:
        verifica_cancelli(*stato(pubblicati=100, fuori_range=5_000), comuni(), n_precedente=None)
    assert nomi_falliti(e) == {"impianti", "prezzi_fuori_range"}


# --- codifica: U+FFFD in more than 0.1% of the rows (0 on the real files of 2026-09-29)

def test_codifica_anagrafica_rovinata_rosso():
    with pytest.raises(CancelloFallito) as e:
        verifica_cancelli(*stato(sostituite_a=25), comuni(), n_precedente=None)  # 25/23,900 = 0.105%
    assert nomi_falliti(e) == {"codifica_anagrafica"}


def test_codifica_prezzi_rovinata_rosso():
    with pytest.raises(CancelloFallito) as e:
        verifica_cancelli(*stato(sostituite_p=100), comuni(), n_precedente=None)  # 100/92,909 = 0.108%
    assert nomi_falliti(e) == {"codifica_prezzi"}


def test_codifica_qualche_carattere_sostituito_verde():
    verifica_cancelli(*stato(sostituite_a=23, sostituite_p=90), comuni(), n_precedente=None)


# --- dati fermi: prezziDel must move forward; stale published data turns the job red

ADESSO = datetime(2026, 9, 30, 7, 15, tzinfo=timezone.utc)
IERI = "2026-09-29T08:00:00+02:00"
OGGI = "2026-09-30T08:00:00+02:00"


def test_prezzi_nuovi_si_pubblica():
    assert valuta_novita(OGGI, IERI, ADESSO) is True


def test_primo_giro_si_pubblica():
    assert valuta_novita(IERI, None, ADESSO) is True


@pytest.mark.parametrize("nuovo", [IERI, "2026-09-28T08:00:00+02:00"])
def test_stesso_giorno_o_indietro_niente_di_nuovo_verde(nuovo):
    assert valuta_novita(nuovo, IERI, ADESSO) is False


def test_dati_fermi_da_meno_di_3_giorni_verde():
    adesso = datetime.fromisoformat(IERI) + MAX_ETA_DATI
    assert valuta_novita(IERI, IERI, adesso) is False


def test_dati_fermi_da_piu_di_3_giorni_rosso():
    adesso = datetime.fromisoformat(IERI) + MAX_ETA_DATI + timedelta(minutes=1)
    with pytest.raises(CancelloFallito) as e:
        valuta_novita(IERI, IERI, adesso)
    assert nomi_falliti(e) == {"dati_fermi"}


def test_dati_nuovi_ma_vecchi_si_pubblicano_comunque():
    # newer than what is online: publishing improves things even if still old
    adesso = datetime(2026, 10, 10, tzinfo=timezone.utc)
    assert valuta_novita(OGGI, IERI, adesso) is True


# --- comuni (comuni.json.gz): national list for the search without GPS

def comuni(n=5_500, nome="X", fuori_bbox=False, lat=40.9, lon=17.3):
    primo = {"n": nome, "p": "BA", "lat": 46.0 if fuori_bbox else lat, "lon": lon, "k": 1}
    return [primo] + [{"n": f"COMUNE {i}", "p": "BA", "lat": lat, "lon": lon, "k": 1} for i in range(n - 1)]


def test_comuni_giornata_reale_passa():
    esiti = verifica_cancelli(*stato(), comuni(), n_precedente=21_200)
    assert {e.nome for e in esiti} >= {"comuni", "comuni_bbox", "comuni_nome_vuoto"}


def test_pochi_comuni_rosso():
    with pytest.raises(CancelloFallito) as e:
        verifica_cancelli(*stato(), comuni(MIN_COMUNI - 1), n_precedente=None)
    assert nomi_falliti(e) == {"comuni"}


def test_comuni_alla_soglia_verde():
    verifica_cancelli(*stato(), comuni(MIN_COMUNI), n_precedente=None)


def test_comune_fuori_dal_bbox_della_sua_provincia_rosso():
    with pytest.raises(CancelloFallito) as e:
        verifica_cancelli(*stato(), comuni(fuori_bbox=True), n_precedente=None)
    assert nomi_falliti(e) == {"comuni_bbox"}


def test_comune_di_provincia_sconosciuta_rosso():
    lista = comuni() + [{"n": "ALTROVE", "p": "ZZ", "lat": 40.9, "lon": 17.3, "k": 1}]
    with pytest.raises(CancelloFallito) as e:
        verifica_cancelli(*stato(), lista, n_precedente=None)
    assert nomi_falliti(e) == {"comuni_bbox"}


def test_comune_senza_nome_rosso():
    with pytest.raises(CancelloFallito) as e:
        verifica_cancelli(*stato(), comuni(nome=""), n_precedente=None)
    assert nomi_falliti(e) == {"comuni_nome_vuoto"}
