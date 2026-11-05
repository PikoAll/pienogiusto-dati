"""Unit tests for the post-publication check, against a real local HTTP server."""
import functools
import http.server
import json
import threading
from pathlib import Path

import pytest

from pienogiusto_dati import verifica_pubblico as vp

PUBBLICO = Path(__file__).resolve().parent.parent / "fixtures" / "pubblico"


class _Silenzioso(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


@pytest.fixture
def base_url():
    handler = functools.partial(_Silenzioso, directory=str(PUBBLICO))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()
    thread.join()


@pytest.fixture
def atteso():
    return json.loads((PUBBLICO / "index_ok.json").read_text(encoding="utf-8"))


def _nessuna_attesa(_s):
    pass


def test_ok(base_url, atteso):
    esito = vp.verifica(base_url + "/index_ok.json", atteso, dormi=_nessuna_attesa)
    assert esito.ok is True
    assert esito.motivo == ""
    assert esito.tentativi == 1


def test_404(base_url, atteso):
    esito = vp.verifica(base_url + "/non_esiste.json", atteso, dormi=_nessuna_attesa)
    assert not esito.ok
    assert "HTTP 404" in esito.motivo


def test_json_rotto(base_url, atteso):
    esito = vp.verifica(base_url + "/index_rotto.json", atteso, dormi=_nessuna_attesa)
    assert not esito.ok
    assert esito.motivo.startswith("JSON non valido")


def test_data_vecchia(base_url, atteso):
    esito = vp.verifica(base_url + "/index_vecchio.json", atteso, dormi=_nessuna_attesa)
    assert not esito.ok
    assert "data vecchia" in esito.motivo
    assert "2026-11-04T08:15:00Z" in esito.motivo
    assert "2026-11-05T08:15:00Z" in esito.motivo


def test_numero_province_diverso(base_url, atteso):
    atteso["province"] = atteso["province"] + [{"sigla": "XX"}] * 104  # 107 expected
    esito = vp.verifica(base_url + "/index_ok.json", atteso, dormi=_nessuna_attesa)
    assert not esito.ok
    assert esito.motivo == "province 3, attese 107"


def test_ritenta_e_dorme_fra_i_tentativi(base_url, atteso):
    attese = []
    esito = vp.verifica(base_url + "/non_esiste.json", atteso, dormi=attese.append)
    assert not esito.ok
    assert esito.tentativi == 3
    assert attese == [30, 30]


def test_si_ferma_al_primo_successo(base_url, atteso):
    attese = []
    esito = vp.verifica(base_url + "/index_ok.json", atteso, dormi=attese.append)
    assert esito.ok and esito.tentativi == 1
    assert attese == []


def test_errore_di_rete(atteso):
    esito = vp.verifica("http://127.0.0.1:1/index.json", atteso, tentativi=1,
                        timeout=2, dormi=_nessuna_attesa)
    assert not esito.ok
    assert esito.motivo


def test_cli_ok(base_url, capsys):
    rc = vp.main(["--url", base_url + "/index_ok.json",
                  "--atteso", str(PUBBLICO / "index_ok.json")])
    assert rc == 0
    assert capsys.readouterr().out.strip() == "verifica-ok"


def test_cli_fallita(base_url, capsys, monkeypatch):
    monkeypatch.setattr(vp.time, "sleep", lambda s: None)
    rc = vp.main(["--url", base_url + "/index_vecchio.json",
                  "--atteso", str(PUBBLICO / "index_ok.json")])
    assert rc == 1
    out = capsys.readouterr().out.strip()
    assert out.startswith("verifica-fallita: data vecchia")


def test_cli_file_atteso_mancante(base_url, tmp_path):
    rc = vp.main(["--url", base_url + "/index_ok.json",
                  "--atteso", str(tmp_path / "manca.json")])
    assert rc == 2


def test_cli_senza_argomenti():
    assert vp.main([]) == 2
