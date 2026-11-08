"""Unit tests for the data-driven gate thresholds (PGD-7): archive, compute, load, gates.

Assumed shape of soglie.json (and of the `soglie` argument of unisci / verifica_cancelli):
{"calcolato_il": ISO timestamp, "giorni": int,
 "prezzi": {"<carburante>": {"min": float, "max": float}}, "impianti_min": {"<sigla>": number}}
Archive layout: <archivio>/AAAA-MM-GG/index.json and <archivio>/AAAA-MM-GG/p/<SIGLA>.json.gz
"""
import gzip
import importlib
import json
import statistics
from collections import Counter
from datetime import date, datetime, timedelta, timezone

import pytest

from pienogiusto_dati.cancelli import MAX_QUOTA_PREZZI_FUORI_RANGE, CancelloFallito, verifica_cancelli
from pienogiusto_dati.parser import Impianto, Prezzo, RisultatoAnagrafica, RisultatoPrezzi
from pienogiusto_dati.unisci import unisci

ADESSO = datetime(2026, 11, 8, 12, 0, tzinfo=timezone.utc)


class _ModuloSoglie:
    """Lazy import: while the module does not exist each test fails on its own, not at collection."""

    def __getattr__(self, nome):
        return getattr(importlib.import_module("pienogiusto_dati.soglie"), nome)


modulo_soglie = _ModuloSoglie()


# --------------------------------------------------------------------------- synthetic archive

def _pgz(impianti):
    return gzip.compress(json.dumps({"schema": 1, "impianti": impianti}).encode("utf-8"), mtime=0)


def scrivi_giorno(radice, giorno, province, prezzi_del=None):
    """province: {sigla: [lista di (carburante, valore) per impianto]}"""
    cartella = radice / giorno.isoformat()
    (cartella / "p").mkdir(parents=True)
    elenco = []
    for sigla, impianti in province.items():
        dati = [{"id": i, "nome": f"N{i}", "band": "B", "ind": "V", "com": "C", "lat": 40.9, "lon": 17.3,
                 "p": [{"c": c, "self": True, "v": v, "t": "2026-11-01T08:00:00"} for c, v in prezzi]}
                for i, prezzi in enumerate(impianti)]
        (cartella / "p" / f"{sigla}.json.gz").write_bytes(_pgz(dati))
        elenco.append({"sigla": sigla, "file": f"p/{sigla}.json.gz", "n": len(impianti),
                       "bbox": [40.9, 17.3, 40.9, 17.3]})
    indice = {"schema": 1, "pubblicato": f"{giorno}T07:00:00Z",
              "prezziDel": prezzi_del or f"{giorno}T08:00:00+01:00", "province": elenco, "comuni": "comuni.json.gz"}
    (cartella / "index.json").write_text(json.dumps(indice))


@pytest.fixture
def archivio_30_giorni(tmp_path):
    """30 recent days (today-0..today-29) + 5 very old days with an absurd Benzina price (9.99)."""
    radice = tmp_path / "archivio"
    radice.mkdir()
    oggi = date.today()
    attesi = {"Benzina": [], "GPL": [], "Metano": [], "Gasolio": []}
    k = 0
    for d in range(30):
        giorno = oggi - timedelta(days=d)
        ba = []
        n_ba = 10 if d % 2 else 20  # median of the daily n = 15 -> impianti_min BA = 12
        for i in range(n_ba):
            prezzi = []
            v = round(1.5 + (k % 200) * 0.005, 3)
            k += 1
            prezzi.append(("Benzina", v))
            attesi["Benzina"].append(v)
            if i < 4:  # 4 per day -> 120 GPL, clamped to the contract floor 0.3
                g = round(0.30 + (d * 4 + i) * 0.00125, 5)
                prezzi.append(("GPL", g))
                attesi["GPL"].append(g)
            if 4 <= i < 8:  # 4 per day -> 120 Metano, clamped to the contract ceiling 4.0
                m = round(3.80 + (d * 4 + i - 4) * 0.0016, 5)
                prezzi.append(("Metano", m))
                attesi["Metano"].append(m)
            if i == 8:  # 1 per day -> 30 Gasolio < 100: excluded
                prezzi.append(("Gasolio", 1.7))
                attesi["Gasolio"].append(1.7)
            ba.append(prezzi)
        to = []
        for _ in range(5):
            v = round(1.6 + (k % 100) * 0.005, 3)
            k += 1
            to.append([("Benzina", v)])
            attesi["Benzina"].append(v)
        scrivi_giorno(radice, giorno, {"BA": ba, "TO": to})
    for d in range(60, 65):
        scrivi_giorno(radice, oggi - timedelta(days=d), {"BA": [[("Benzina", 9.99)]] * 10})
    return radice, attesi


def _quantili(valori):
    q = statistics.quantiles(valori, n=100, method="inclusive")
    return q[0], q[98]


def lancia_calcola(radice, uscita):
    return modulo_soglie.main(["calcola", "--archivio", str(radice), "--uscita", str(uscita)])


# --------------------------------------------------------------------------- calcola

def test_calcola_crea_il_file_con_i_campi_richiesti(tmp_path, archivio_30_giorni):
    radice, _ = archivio_30_giorni
    uscita = tmp_path / "config" / "soglie.json"
    uscita.parent.mkdir()
    assert lancia_calcola(radice, uscita) == 0
    dati = json.loads(uscita.read_text())
    assert {"calcolato_il", "giorni", "prezzi", "impianti_min"} <= set(dati)
    assert dati["giorni"] == 30  # the 5 old days are outside the 30-day window
    assert isinstance(dati["calcolato_il"], str) and dati["calcolato_il"]


def test_calcola_percentili_meno_dieci_per_cento(tmp_path, archivio_30_giorni):
    radice, attesi = archivio_30_giorni
    uscita = tmp_path / "config" / "soglie.json"
    uscita.parent.mkdir()
    lancia_calcola(radice, uscita)
    benzina = json.loads(uscita.read_text())["prezzi"]["Benzina"]
    p1, p99 = _quantili(attesi["Benzina"])
    assert benzina["min"] == pytest.approx(p1 * 0.9, abs=0.005)
    assert benzina["max"] == pytest.approx(p99 * 1.1, abs=0.005)  # old 9.99 prices are ignored


def test_calcola_restringe_al_range_del_contratto(tmp_path, archivio_30_giorni):
    radice, attesi = archivio_30_giorni
    uscita = tmp_path / "config" / "soglie.json"
    uscita.parent.mkdir()
    lancia_calcola(radice, uscita)
    prezzi = json.loads(uscita.read_text())["prezzi"]
    assert prezzi["GPL"]["min"] == pytest.approx(0.3)  # 1st percentile - 10% would be < 0.3
    assert prezzi["GPL"]["max"] == pytest.approx(_quantili(attesi["GPL"])[1] * 1.1, abs=0.005)
    assert prezzi["Metano"]["max"] == pytest.approx(4.0)  # 99th percentile + 10% would be > 4.0
    assert prezzi["Metano"]["min"] == pytest.approx(_quantili(attesi["Metano"])[0] * 0.9, abs=0.005)


def test_calcola_esclude_carburante_con_meno_di_100_prezzi(tmp_path, archivio_30_giorni):
    radice, attesi = archivio_30_giorni
    assert len(attesi["Gasolio"]) < 100
    uscita = tmp_path / "config" / "soglie.json"
    uscita.parent.mkdir()
    lancia_calcola(radice, uscita)
    prezzi = json.loads(uscita.read_text())["prezzi"]
    assert "Gasolio" not in prezzi
    assert {"Benzina", "GPL", "Metano"} <= set(prezzi)


def test_calcola_impianti_min_e_80_per_cento_della_mediana_giornaliera(tmp_path, archivio_30_giorni):
    radice, _ = archivio_30_giorni
    uscita = tmp_path / "config" / "soglie.json"
    uscita.parent.mkdir()
    lancia_calcola(radice, uscita)
    minimi = json.loads(uscita.read_text())["impianti_min"]
    assert minimi["BA"] == pytest.approx(12.0)  # median(10, 20 alternating) = 15 -> 80% = 12
    assert minimi["TO"] == pytest.approx(4.0)  # constant 5 -> 80% = 4


def _archivio_con_giorni(tmp_path, giorni):
    radice = tmp_path / "archivio"
    radice.mkdir()
    for d in range(giorni):
        scrivi_giorno(radice, date.today() - timedelta(days=d), {"BA": [[("Benzina", 1.8)]] * 10})
    return radice


def test_calcola_con_meno_di_7_giorni_esce_0_senza_file_e_spiega(tmp_path, capsys, caplog):
    radice = _archivio_con_giorni(tmp_path, 6)
    uscita = tmp_path / "config" / "soglie.json"
    uscita.parent.mkdir()
    assert lancia_calcola(radice, uscita) == 0
    assert not uscita.exists()
    fuori = capsys.readouterr()
    assert (fuori.out + fuori.err + caplog.text).strip(), "the reason must be logged"


def test_calcola_con_7_giorni_crea_il_file(tmp_path):
    radice = _archivio_con_giorni(tmp_path, 7)
    uscita = tmp_path / "config" / "soglie.json"
    uscita.parent.mkdir()
    assert lancia_calcola(radice, uscita) == 0
    assert json.loads(uscita.read_text())["giorni"] == 7


# --------------------------------------------------------------------------- archivia

def _sorgente(tmp_path, prezzi_del="2026-11-01T08:00:00+01:00"):
    sorgente = tmp_path / "pubblicato"
    (sorgente / "p").mkdir(parents=True)
    (sorgente / "p" / "BA.json.gz").write_bytes(_pgz([{"id": 1, "p": [{"c": "Benzina", "v": 1.8}]}]))
    (sorgente / "p" / "TO.json.gz").write_bytes(_pgz([{"id": 2, "p": [{"c": "Benzina", "v": 1.9}]}]))
    indice = {"schema": 1, "prezziDel": prezzi_del, "comuni": "comuni.json.gz",
              "province": [{"sigla": s, "file": f"p/{s}.json.gz", "n": 1, "bbox": [0, 0, 0, 0]}
                           for s in ("BA", "TO")]}
    (sorgente / "index.json").write_text(json.dumps(indice))
    return sorgente


def lancia_archivia(sorgente, archivio):
    return modulo_soglie.main(["archivia", "--base-url", f"file://{sorgente}", "--archivio", str(archivio)])


def test_archivia_salva_indice_e_province_nel_giorno_di_prezzi_del(tmp_path):
    sorgente = _sorgente(tmp_path)
    archivio = tmp_path / "arch"
    assert lancia_archivia(sorgente, archivio) == 0
    giorno = archivio / "2026-11-01"
    assert (giorno / "index.json").read_bytes() == (sorgente / "index.json").read_bytes()
    for sigla in ("BA", "TO"):
        assert (giorno / "p" / f"{sigla}.json.gz").read_bytes() == (sorgente / "p" / f"{sigla}.json.gz").read_bytes()
    # written in a temp dir then renamed: nothing else is left in the archive
    assert [p.name for p in archivio.iterdir()] == ["2026-11-01"]


def test_archivia_rilanciato_stesso_giorno_esce_0_e_non_riscarica(tmp_path):
    sorgente = _sorgente(tmp_path)
    archivio = tmp_path / "arch"
    lancia_archivia(sorgente, archivio)
    originale = (archivio / "2026-11-01" / "p" / "BA.json.gz").read_bytes()
    (sorgente / "p" / "BA.json.gz").write_bytes(_pgz([{"id": 99, "p": []}]))  # source changes: must NOT be fetched
    assert lancia_archivia(sorgente, archivio) == 0
    assert (archivio / "2026-11-01" / "p" / "BA.json.gz").read_bytes() == originale


def test_archivia_non_tocca_i_giorni_vecchi(tmp_path):
    sorgente = _sorgente(tmp_path)
    archivio = tmp_path / "arch"
    vecchio = archivio / "2026-10-01"
    vecchio.mkdir(parents=True)
    (vecchio / "index.json").write_text("{}")
    assert lancia_archivia(sorgente, archivio) == 0
    assert (vecchio / "index.json").read_text() == "{}"
    assert sorted(p.name for p in archivio.iterdir()) == ["2026-10-01", "2026-11-01"]


def test_archivia_con_provincia_irraggiungibile_fallisce_senza_giorno_parziale(tmp_path):
    sorgente = _sorgente(tmp_path)
    (sorgente / "p" / "TO.json.gz").rename(sorgente / "p" / "TO.json.gz.backup")
    archivio = tmp_path / "arch"
    assert lancia_archivia(sorgente, archivio) != 0
    assert not (archivio / "2026-11-01").exists()


# --------------------------------------------------------------------------- carica (fallback to constants)

def _file_soglie(tmp_path, giorni=30, eta_giorni=1, nome="soglie.json"):
    f = tmp_path / nome
    f.write_text(json.dumps({"calcolato_il": (ADESSO - timedelta(days=eta_giorni)).isoformat(), "giorni": giorni,
                             "prezzi": {"Benzina": {"min": 1.0, "max": 2.5}}, "impianti_min": {"BA": 10}}))
    return f


def test_carica_file_valido_restituisce_le_soglie(tmp_path):
    soglie = modulo_soglie.carica(_file_soglie(tmp_path), ADESSO)
    assert soglie["prezzi"]["Benzina"] == {"min": 1.0, "max": 2.5}
    assert soglie["impianti_min"] == {"BA": 10}


def test_carica_file_di_45_giorni_e_ancora_valido(tmp_path):
    assert modulo_soglie.carica(_file_soglie(tmp_path, eta_giorni=45), ADESSO) is not None


def _motivo_loggato(capsys, caplog):
    fuori = capsys.readouterr()
    return (fuori.out + fuori.err + caplog.text).strip()


def test_carica_file_mancante_ripiega_e_spiega(tmp_path, capsys, caplog):
    assert modulo_soglie.carica(tmp_path / "non-esiste.json", ADESSO) is None
    assert _motivo_loggato(capsys, caplog)


def test_carica_file_illeggibile_ripiega_e_spiega(tmp_path, capsys, caplog):
    f = tmp_path / "soglie.json"
    f.write_text("{non e' json")
    assert modulo_soglie.carica(f, ADESSO) is None
    assert _motivo_loggato(capsys, caplog)


def test_carica_con_5_giorni_ripiega_e_spiega(tmp_path, capsys, caplog):
    assert modulo_soglie.carica(_file_soglie(tmp_path, giorni=5), ADESSO) is None
    assert _motivo_loggato(capsys, caplog)


def test_carica_file_di_46_giorni_ripiega_e_spiega(tmp_path, capsys, caplog):
    assert modulo_soglie.carica(_file_soglie(tmp_path, eta_giorni=46), ADESSO) is None
    assert _motivo_loggato(capsys, caplog)


# --------------------------------------------------------------------------- gates with soglie

def _imp(id_, prov="BA"):
    return Impianto(id_, f"N{id_}", "Q8", "VIA", "COM", prov, 40.95, 17.30)


def _unione(prezzi_per_impianto, soglie=None, prov="BA"):
    impianti = [_imp(i, prov) for i in range(len(prezzi_per_impianto))]
    a = RisultatoAnagrafica(None, "|", "utf-8", len(impianti), {i.id: i for i in impianti}, Counter())
    p = RisultatoPrezzi(None, "|", "utf-8", max(1, sum(len(x) for x in prezzi_per_impianto)),
                        {i: [Prezzo(c, True, v, "2026-11-01T08:00:00") for c, v in lista]
                         for i, lista in enumerate(prezzi_per_impianto)}, Counter())
    return (a, p, unisci(a, p, soglie=soglie)) if soglie is not None else (a, p, unisci(a, p))


def _comuni():
    return [{"n": f"COMUNE {i}", "p": "BA", "lat": 40.95, "lon": 17.30, "k": 1} for i in range(5_000)]


SOGLIE_BENZINA = {"calcolato_il": ADESSO.isoformat(), "giorni": 30,
                  "prezzi": {"Benzina": {"min": 1.0, "max": 2.0}}, "impianti_min": {}}


def test_unisci_scarta_prezzo_dentro_contratto_ma_fuori_soglie():
    _, _, u = _unione([[("Benzina", 2.5)], [("Benzina", 1.5)]], SOGLIE_BENZINA)
    assert u.scarti["prezzo_fuori_range"] == 1
    assert u.pubblicati == 1


def test_unisci_senza_soglie_tiene_lo_stesso_prezzo():
    _, _, u = _unione([[("Benzina", 2.5)], [("Benzina", 1.5)]])
    assert u.scarti["prezzo_fuori_range"] == 0
    assert u.pubblicati == 2


def test_unisci_con_soglie_non_tocca_i_carburanti_assenti_dal_file():
    _, _, u = _unione([[("Gasolio", 3.5)]], SOGLIE_BENZINA)
    assert u.scarti["prezzo_fuori_range"] == 0 and u.pubblicati == 1


def _mille_con_fuori_soglia(k):
    return [[("Benzina", 3.0 if i < k else 1.5)] for i in range(1000)]


def test_quota_fuori_soglie_entro_il_limite_il_cancello_passa():
    k = int(MAX_QUOTA_PREZZI_FUORI_RANGE * 1000)  # exactly at the limit
    a, p, u = _unione(_mille_con_fuori_soglia(k), SOGLIE_BENZINA)
    assert u.scarti["prezzo_fuori_range"] == k
    esiti = verifica_cancelli(a, p, u, _comuni(), n_precedente=u.pubblicati, soglie=SOGLIE_BENZINA)
    assert all(e.ok for e in esiti)


def test_quota_fuori_soglie_sopra_il_limite_il_cancello_fallisce_anche_se_dentro_le_vecchie_costanti():
    k = int(MAX_QUOTA_PREZZI_FUORI_RANGE * 1000) + 5
    dati = _mille_con_fuori_soglia(k)
    # with the old constants the very same day is green
    a0, p0, u0 = _unione(dati)
    verifica_cancelli(a0, p0, u0, _comuni(), n_precedente=u0.pubblicati)
    a, p, u = _unione(dati, SOGLIE_BENZINA)
    with pytest.raises(CancelloFallito) as e:
        verifica_cancelli(a, p, u, _comuni(), n_precedente=u.pubblicati, soglie=SOGLIE_BENZINA)
    assert {x.nome for x in e.value.falliti} == {"prezzi_fuori_range"}


def _soglie_impianti(minimi):
    return {**SOGLIE_BENZINA, "impianti_min": minimi}


def test_impianti_provincia_sotto_il_minimo_fallisce():
    soglie = _soglie_impianti({"BA": 11})
    a, p, u = _unione([[("Benzina", 1.5)]] * 10, soglie)
    with pytest.raises(CancelloFallito) as e:
        verifica_cancelli(a, p, u, _comuni(), n_precedente=10, soglie=soglie)
    assert {x.nome for x in e.value.falliti} == {"impianti_provincia"}


def test_impianti_provincia_assente_vale_zero_e_fallisce():
    soglie = _soglie_impianti({"BA": 10, "TO": 4})
    a, p, u = _unione([[("Benzina", 1.5)]] * 10, soglie)
    with pytest.raises(CancelloFallito) as e:
        verifica_cancelli(a, p, u, _comuni(), n_precedente=10, soglie=soglie)
    assert {x.nome for x in e.value.falliti} == {"impianti_provincia"}


def test_impianti_provincia_al_minimo_passa_e_compare_negli_esiti():
    soglie = _soglie_impianti({"BA": 10})
    a, p, u = _unione([[("Benzina", 1.5)]] * 10, soglie)
    esiti = verifica_cancelli(a, p, u, _comuni(), n_precedente=10, soglie=soglie)
    assert "impianti_provincia" in {e.nome for e in esiti}
    assert all(e.ok for e in esiti)


def test_senza_soglie_nessun_cancello_impianti_provincia():
    a, p, u = _unione([[("Benzina", 1.5)]] * 10)
    esiti = verifica_cancelli(a, p, u, _comuni(), n_precedente=10)
    assert "impianti_provincia" not in {e.nome for e in esiti}
    assert verifica_cancelli(a, p, u, _comuni(), n_precedente=10, soglie=None) is not None
