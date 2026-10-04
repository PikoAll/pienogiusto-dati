"""Integration tests: whole pipeline on the real 2026-09-29 extract, from bytes to site/ on disk."""
import gzip
import json
from pathlib import Path
from datetime import datetime, timezone

import pytest

from pienogiusto_dati import cancelli
from pienogiusto_dati.pubblica import main

FIXTURES = Path(__file__).parents[1] / "fixtures"
ADESSO = datetime(2026, 9, 30, 7, 10, tzinfo=timezone.utc)


@pytest.fixture
def soglia_bassa(monkeypatch):
    # the fixture has ~160 stations, not 21,000, and concentrates on purpose 8 real
    # out-of-range prices (~0.9% of its rows vs 0.013% in the full file)
    monkeypatch.setattr(cancelli, "MIN_IMPIANTI_ASSOLUTO", 100)
    monkeypatch.setattr(cancelli, "MAX_QUOTA_PREZZI_FUORI_RANGE", 0.05)
    monkeypatch.setattr(cancelli, "MIN_COMUNI", 10)  # ~20 municipalities in the fixture, not 5,000


def lancia(tmp_path, anagrafica="anagrafica_reale.csv", prezzi="prezzi_reale.csv", *extra):
    uscita = tmp_path / "site"
    codice = main(["--anagrafica", str(FIXTURES / anagrafica), "--prezzi", str(FIXTURES / prezzi),
                   "--uscita", str(uscita), "--adesso", ADESSO.isoformat(), *extra])
    return codice, uscita


def test_pipeline_scrive_index_province_e_report(tmp_path, soglia_bassa):
    codice, site = lancia(tmp_path)
    assert codice == 0
    index = json.loads((site / "index.json").read_text())
    assert index["schema"] == 1
    assert index["pubblicato"] == "2026-09-30T07:10:00Z"
    assert index["prezziDel"] == "2026-09-29T08:00:00+02:00"
    sigle = [p["sigla"] for p in index["province"]]
    assert sigle == sorted(sigle) and "BA" in sigle
    ba = next(p for p in index["province"] if p["sigla"] == "BA")
    assert ba["file"] == "p/BA.json.gz"
    dati = json.loads(gzip.decompress((site / ba["file"]).read_bytes()))
    assert dati["schema"] == 1 and len(dati["impianti"]) == ba["n"]
    report = json.loads((site / "report.json").read_text())
    assert report["impianti_pubblicati"] == sum(p["n"] for p in index["province"])
    assert report["scarti"]["coordinate_mancanti"] == 3
    assert report["scarti"]["prezzo_fuori_range"] == 8  # 4 of the 6 real outlier stations are in the fixture
    assert set(report["cancelli"]) >= {"impianti", "coordinate_valide"}
    assert "durata_s" in report
    assert "IODL" in (site / "LEGGIMI.txt").read_text()


def test_pipeline_scrive_elenco_comuni(tmp_path, soglia_bassa):
    _, site = lancia(tmp_path)
    index = json.loads((site / "index.json").read_text())
    assert index["comuni"] == "comuni.json.gz"
    comuni = json.loads(gzip.decompress((site / "comuni.json.gz").read_bytes()))["comuni"]
    acquaviva = next(c for c in comuni if c["n"] == "ACQUAVIVA DELLE FONTI")
    assert acquaviva["p"] == "BA" and acquaviva["k"] >= 5
    assert 40.88 <= acquaviva["lat"] <= 40.91 and 16.83 <= acquaviva["lon"] <= 16.88
    report = json.loads((site / "report.json").read_text())
    assert report["comuni"] == len(comuni)
    assert report["cancelli"]["comuni"]["ok"] is True


def test_casi_difficili_reali_recuperati(tmp_path, soglia_bassa):
    _, site = lancia(tmp_path)
    tutti = {}
    for f in (site / "p").glob("*.json.gz"):
        for d in json.loads(gzip.decompress(f.read_bytes()))["impianti"]:
            tutti[d["id"]] = d
    assert tutti[40820]["nome"] == "STOIL SIMPLE"           # separator inside the name
    assert tutti[54386]["com"] == "ZOCCA"                   # separator in gestore and name
    assert tutti[46593]["band"] == "Q8"                     # unbalanced double quote
    assert tutti[63381]["nome"] == "19834 MONTALLEGRO"      # tab inside the name


def test_gzip_deterministico(tmp_path, soglia_bassa):
    _, a = lancia(tmp_path / "a")
    _, b = lancia(tmp_path / "b")
    assert (a / "p" / "BA.json.gz").read_bytes() == (b / "p" / "BA.json.gz").read_bytes()


def test_cancello_fallito_exit_1_e_niente_su_disco(tmp_path):
    # without lowering the floor, 160 stations < 18,000
    codice, site = lancia(tmp_path)
    assert codice == 1
    assert not site.exists()
    assert list(tmp_path.iterdir()) == []


def precedente(tmp_path, n, prezzi_del):
    prec = tmp_path / "prec.json"
    prec.write_text(json.dumps({"schema": 1, "prezziDel": prezzi_del, "province": [{"sigla": "BA", "n": n}]}))
    return prec


def test_indice_precedente_confrontato(tmp_path, soglia_bassa):
    prec = precedente(tmp_path, 10_000, "2026-09-28T08:00:00+02:00")
    codice, site = lancia(tmp_path, "anagrafica_reale.csv", "prezzi_reale.csv",
                          "--indice-precedente", prec.as_uri())
    assert codice == 1 and not site.exists()


def test_html_al_posto_del_csv_exit_1(tmp_path, soglia_bassa):
    codice, site = lancia(tmp_path, "pagina_errore.html")
    assert codice == 1 and not site.exists()


def test_uscita_gia_esistente_non_viene_toccata(tmp_path, soglia_bassa):
    site = tmp_path / "site"
    site.mkdir()
    (site / "vecchio.txt").write_text("resta")
    codice, _ = lancia(tmp_path)
    assert codice == 2
    assert (site / "vecchio.txt").read_text() == "resta"


def test_niente_di_nuovo_exit_0_senza_site_e_output_per_il_workflow(tmp_path, soglia_bassa, monkeypatch):
    out = tmp_path / "github_output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    prec = precedente(tmp_path, 149, "2026-09-29T08:00:00+02:00")
    codice, site = lancia(tmp_path, "anagrafica_reale.csv", "prezzi_reale.csv",
                          "--indice-precedente", prec.as_uri())
    assert codice == 0 and not site.exists()
    assert out.read_text() == "nuovo=false\n"


def test_dati_nuovi_output_nuovo_true(tmp_path, soglia_bassa, monkeypatch):
    out = tmp_path / "github_output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    prec = precedente(tmp_path, 149, "2026-09-28T08:00:00+02:00")
    codice, site = lancia(tmp_path, "anagrafica_reale.csv", "prezzi_reale.csv",
                          "--indice-precedente", prec.as_uri())
    assert codice == 0 and site.is_dir()
    assert out.read_text() == "nuovo=true\n"


def test_dati_fermi_da_giorni_exit_1(tmp_path, soglia_bassa):
    prec = precedente(tmp_path, 149, "2026-09-29T08:00:00+02:00")
    uscita = tmp_path / "site"
    codice = main(["--anagrafica", str(FIXTURES / "anagrafica_reale.csv"),
                   "--prezzi", str(FIXTURES / "prezzi_reale.csv"), "--uscita", str(uscita),
                   "--adesso", "2026-10-03T07:15:00+00:00", "--indice-precedente", prec.as_uri()])
    assert codice == 1 and not uscita.exists()
