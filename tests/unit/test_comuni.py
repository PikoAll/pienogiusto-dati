"""Unit tests for the national list of municipalities (comuni.json.gz)."""
from collections import Counter

from pienogiusto_dati.comuni import elenco_comuni, media, normalizza_nome
from pienogiusto_dati.unisci import Unione


def punto(com, prov="BA", lat=40.95, lon=17.30):
    return {"id": 1, "nome": "", "band": "Q8", "ind": "VIA", "com": com, "lat": lat, "lon": lon, "p": []}


def unione(**province):
    return Unione(province=province, scarti=Counter())


# --- normalizza_nome: trim, single spaces, case kept as in the data

def test_normalizza_toglie_spazi_ai_bordi_e_doppi():
    assert normalizza_nome("  ACQUAVIVA   DELLE\tFONTI ") == "ACQUAVIVA DELLE FONTI"


def test_normalizza_non_cambia_maiuscole_minuscole():
    assert normalizza_nome("Monopoli") == "Monopoli"


def test_normalizza_stringa_vuota_resta_vuota():
    assert normalizza_nome("   ") == ""


# --- media: arithmetic mean rounded to 5 decimals

def test_media_arrotondata_a_5_decimali():
    assert media([40.123456, 40.123458]) == 40.12346


def test_media_di_un_solo_valore():
    assert media([17.3]) == 17.3


# --- elenco_comuni

def test_un_comune_per_coppia_nome_provincia_con_media_e_conteggio():
    u = unione(BA=[punto("MONOPOLI", lat=40.9, lon=17.2), punto("MONOPOLI", lat=41.0, lon=17.4)])
    assert elenco_comuni(u) == [{"n": "MONOPOLI", "p": "BA", "lat": 40.95, "lon": 17.3, "k": 2}]


def test_stesso_nome_in_due_province_due_voci():
    u = unione(BA=[punto("SAN GIORGIO")], BR=[punto("SAN GIORGIO", "BR", 40.6, 17.9)])
    voci = elenco_comuni(u)
    assert [(v["n"], v["p"]) for v in voci] == [("SAN GIORGIO", "BA"), ("SAN GIORGIO", "BR")]


def test_ordinato_per_nome_poi_provincia():
    u = unione(BR=[punto("ZOCCA", "BR"), punto("ALBA", "BR")], BA=[punto("ALBA")])
    assert [(v["n"], v["p"]) for v in elenco_comuni(u)] == [("ALBA", "BA"), ("ALBA", "BR"), ("ZOCCA", "BR")]


def test_nomi_con_spazi_diversi_confluiscono_nella_stessa_voce():
    u = unione(BA=[punto("ACQUAVIVA  DELLE FONTI"), punto(" ACQUAVIVA DELLE FONTI")])
    (v,) = elenco_comuni(u)
    assert v["n"] == "ACQUAVIVA DELLE FONTI" and v["k"] == 2


def test_nome_vuoto_resta_nella_lista_per_il_cancello():
    # the gate `comuni_nome_vuoto` must see it: the list does not hide it
    u = unione(BA=[punto("  ")])
    assert elenco_comuni(u) == [{"n": "", "p": "BA", "lat": 40.95, "lon": 17.3, "k": 1}]


def test_unione_vuota_lista_vuota():
    assert elenco_comuni(unione()) == []
