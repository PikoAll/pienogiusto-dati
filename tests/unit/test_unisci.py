"""Unit tests for the join anagrafica+prezzi and the per-province grouping."""
from collections import Counter

from pienogiusto_dati.parser import Impianto, Prezzo, RisultatoAnagrafica, RisultatoPrezzi
from pienogiusto_dati.unisci import unisci


def imp(id_, prov="BA", lat=40.95, lon=17.30):
    return Impianto(id_, f"N{id_}", "Q8", "VIA", "COM", prov, lat, lon)


def pz(c="Gasolio", self=True, v=1.679):
    return Prezzo(c, self, v, "2026-09-28T19:12:00")


def run(impianti, prezzi):
    a = RisultatoAnagrafica(None, "|", "utf-8", len(impianti), {i.id: i for i in impianti}, Counter())
    p = RisultatoPrezzi(None, "|", "utf-8", 0, prezzi, Counter())
    return unisci(a, p)


def test_impianto_con_prezzi_finisce_nella_sua_provincia():
    r = run([imp(1), imp(2, prov="BR", lat=40.6, lon=17.9)], {1: [pz()], 2: [pz()]})
    assert sorted(r.province) == ["BA", "BR"]
    assert r.province["BA"][0]["id"] == 1
    assert r.pubblicati == 2


def test_formato_chiavi_corte():
    r = run([imp(1)], {1: [pz("Gasolio", False, 1.8), pz("Benzina", True, 1.7)]})
    (d,) = r.province["BA"]
    assert d == {"id": 1, "nome": "N1", "band": "Q8", "ind": "VIA", "com": "COM", "lat": 40.95, "lon": 17.3,
                 "p": [{"c": "Benzina", "self": True, "v": 1.7, "t": "2026-09-28T19:12:00"},
                       {"c": "Gasolio", "self": False, "v": 1.8, "t": "2026-09-28T19:12:00"}]}


def test_coordinate_arrotondate_a_5_decimali():
    r = run([imp(1, lat=40.123456789, lon=17.987654321)], {1: [pz()]})
    d = r.province["BA"][0]
    assert (d["lat"], d["lon"]) == (40.12346, 17.98765)


def test_senza_coordinate_scartato():
    r = run([imp(1, lat=None, lon=None)], {1: [pz()]})
    assert r.province == {} and r.scarti["coordinate_mancanti"] == 1


def test_coordinate_zero_contano_come_mancanti():
    r = run([imp(1, lat=0.0, lon=0.0)], {1: [pz()]})
    assert r.scarti["coordinate_mancanti"] == 1


def test_coordinate_fuori_italia_scartate():
    # swapped lat/lon is the typical data-entry error
    r = run([imp(1, lat=17.30, lon=40.95)], {1: [pz()]})
    assert r.province == {} and r.scarti["coordinate_fuori_italia"] == 1


def test_senza_prezzi_scartato():
    r = run([imp(1)], {})
    assert r.province == {} and r.scarti["senza_prezzi"] == 1


def test_prezzo_fuori_range_scartato_il_resto_resta():
    r = run([imp(1)], {1: [pz(v=0.1), pz("GPL", False, 0.849), pz("Metano", False, 8.888)]})
    assert [p["c"] for p in r.province["BA"][0]["p"]] == ["GPL"]
    assert r.scarti["prezzo_fuori_range"] == 2
    assert r.prezzi_totali == 3


def test_solo_prezzi_fuori_range_diventa_senza_prezzi():
    r = run([imp(1)], {1: [pz(v=0.1)]})
    assert r.province == {} and r.scarti["senza_prezzi"] == 1


def test_prezzi_senza_impianto_contati():
    r = run([imp(1)], {1: [pz()], 99: [pz(), pz("GPL")]})
    assert r.scarti["prezzi_senza_impianto"] == 2


def test_con_coordinate_valide_conta_anche_chi_non_ha_prezzi():
    r = run([imp(1), imp(2), imp(3, lat=None, lon=None)], {1: [pz()]})
    assert r.con_coordinate_valide == 2
    assert r.anagrafica == 3


def test_bbox_provincia():
    r = run([imp(1, lat=40.73, lon=17.49), imp(2, lat=41.33, lon=16.07)], {1: [pz()], 2: [pz()]})
    assert r.bbox("BA") == [40.73, 16.07, 41.33, 17.49]


def test_impianti_ordinati_per_id():
    r = run([imp(5), imp(2), imp(9)], {5: [pz()], 2: [pz()], 9: [pz()]})
    assert [d["id"] for d in r.province["BA"]] == [2, 5, 9]
