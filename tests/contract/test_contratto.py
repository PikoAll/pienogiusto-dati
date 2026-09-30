"""Contract test app <-> data, schema 1 (docs/CONTRATTO.md).

By default it validates a site/ built from the fixtures. With PIENOGIUSTO_SITE=<dir>
it validates a real build (the publish workflow runs it on site/ before deploying).
"""
import gzip
import json
import os
import re
from datetime import datetime
from pathlib import Path

import pytest

from pienogiusto_dati import cancelli
from pienogiusto_dati.pubblica import main
from pienogiusto_dati.unisci import in_italia

FIXTURES = Path(__file__).parents[1] / "fixtures"
CHIAVI_INDEX = {"schema", "pubblicato", "prezziDel", "province"}
CHIAVI_PROVINCIA = {"sigla", "file", "n", "bbox"}
CHIAVI_IMPIANTO = {"id", "nome", "band", "ind", "com", "lat", "lon", "p"}
CHIAVI_PREZZO = {"c", "self", "v", "t"}


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    reale = os.environ.get("PIENOGIUSTO_SITE")
    if reale:
        return Path(reale)
    uscita = tmp_path_factory.mktemp("contratto") / "site"
    mp = pytest.MonkeyPatch()
    mp.setattr(cancelli, "MIN_IMPIANTI_ASSOLUTO", 100)
    mp.setattr(cancelli, "MAX_QUOTA_PREZZI_FUORI_RANGE", 0.05)
    try:
        assert main(["--anagrafica", str(FIXTURES / "anagrafica_reale.csv"),
                     "--prezzi", str(FIXTURES / "prezzi_reale.csv"), "--uscita", str(uscita)]) == 0
    finally:
        mp.undo()
    return uscita


@pytest.fixture(scope="module")
def index(site):
    return json.loads((site / "index.json").read_text(encoding="utf-8"))


def carica(site, voce):
    return json.loads(gzip.decompress((site / voce["file"]).read_bytes()))


def test_index_schema_1(index):
    assert set(index) == CHIAVI_INDEX
    assert index["schema"] == 1
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", index["pubblicato"])
    prezzi_del = datetime.fromisoformat(index["prezziDel"])
    assert prezzi_del.utcoffset() is not None and (prezzi_del.hour, prezzi_del.minute) == (8, 0)
    assert index["province"]


def test_voci_provincia(index, site):
    sigle = [p["sigla"] for p in index["province"]]
    assert sigle == sorted(set(sigle))
    for v in index["province"]:
        assert set(v) == CHIAVI_PROVINCIA
        assert re.fullmatch(r"[A-Z]{2}", v["sigla"])
        assert v["file"] == f"p/{v['sigla']}.json.gz" and (site / v["file"]).is_file()
        assert isinstance(v["n"], int) and v["n"] > 0
        min_lat, min_lon, max_lat, max_lon = v["bbox"]
        assert min_lat <= max_lat and min_lon <= max_lon
        assert in_italia(min_lat, min_lon) and in_italia(max_lat, max_lon)


def test_file_provincia_ba(index, site):
    """The file the app is developed against (Monopoli is in BA)."""
    voce = next(v for v in index["province"] if v["sigla"] == "BA")
    verifica_file_provincia(voce, carica(site, voce))


def test_tutti_i_file_provincia(index, site):
    for voce in index["province"]:
        verifica_file_provincia(voce, carica(site, voce))


def verifica_file_provincia(voce, dati):
    assert set(dati) == {"schema", "impianti"} and dati["schema"] == 1
    assert len(dati["impianti"]) == voce["n"]
    min_lat, min_lon, max_lat, max_lon = voce["bbox"]
    ids = [d["id"] for d in dati["impianti"]]
    assert ids == sorted(set(ids))
    for d in dati["impianti"]:
        assert set(d) == CHIAVI_IMPIANTO, d
        assert isinstance(d["id"], int)
        assert all(isinstance(d[k], str) for k in ("nome", "band", "ind", "com"))
        assert d["com"]
        assert isinstance(d["lat"], float) and isinstance(d["lon"], float)
        assert min_lat <= d["lat"] <= max_lat and min_lon <= d["lon"] <= max_lon
        assert d["p"]
        for p in d["p"]:
            assert set(p) == CHIAVI_PREZZO
            assert isinstance(p["c"], str) and p["c"]
            assert isinstance(p["self"], bool)
            assert isinstance(p["v"], float) and 0.3 <= p["v"] <= 4.0
            t = datetime.fromisoformat(p["t"])
            assert t.utcoffset() is None  # local Rome time, no offset, as in the contract example
