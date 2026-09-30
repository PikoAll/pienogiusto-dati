"""Unit tests for the robust downloader (network replaced by fakes)."""
import io
import urllib.error

import pytest

from pienogiusto_dati.scarica import ErroreDownload, USER_AGENT, indice_precedente, scarica


class Risposta(io.BytesIO):
    def __init__(self, corpo: bytes, tipo="text/csv", lunghezza: int | None = -1, status=200):
        super().__init__(corpo)
        self.status = status
        self.headers = {"Content-Type": tipo}
        if lunghezza == -1:
            lunghezza = len(corpo)
        if lunghezza is not None:
            self.headers["Content-Length"] = str(lunghezza)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class Apri:
    """Fake urlopen: returns/raises the queued items in order and records requests."""

    def __init__(self, *esiti):
        self.esiti = list(esiti)
        self.richieste = []

    def __call__(self, req, timeout):
        self.richieste.append((req, timeout))
        e = self.esiti.pop(0)
        if isinstance(e, Exception):
            raise e
        return e


CSV = b"idImpianto|x\n1|a\n"


def test_scarica_ok_con_user_agent_e_timeout():
    apri = Apri(Risposta(CSV))
    assert scarica("https://x/a.csv", apri=apri, dormi=lambda s: None) == CSV
    req, timeout = apri.richieste[0]
    assert req.get_header("User-agent") == USER_AGENT
    assert timeout > 0


def test_riprova_con_attesa_crescente_poi_riesce():
    attese = []
    apri = Apri(urllib.error.URLError("dns"), TimeoutError("lento"), Risposta(CSV))
    assert scarica("https://x/a.csv", apri=apri, dormi=attese.append) == CSV
    assert len(attese) == 2 and attese[0] < attese[1]


def test_tre_fallimenti_errore():
    apri = Apri(*(urllib.error.URLError("giu") for _ in range(3)))
    with pytest.raises(ErroreDownload, match="3 tentativi"):
        scarica("https://x/a.csv", apri=apri, dormi=lambda s: None)
    assert len(apri.richieste) == 3


def test_pagina_html_rifiutata_per_content_type():
    apri = Apri(*(Risposta(b"<html>errore</html>", tipo="text/html; charset=utf-8") for _ in range(3)))
    with pytest.raises(ErroreDownload, match="HTML"):
        scarica("https://x/a.csv", apri=apri, dormi=lambda s: None)


def test_pagina_html_rifiutata_anche_se_dichiarata_csv():
    apri = Apri(*(Risposta(b"  <!DOCTYPE html><html>", tipo="text/csv") for _ in range(3)))
    with pytest.raises(ErroreDownload, match="HTML"):
        scarica("https://x/a.csv", apri=apri, dormi=lambda s: None)


def test_risposta_troncata_rifiutata():
    apri = Apri(*(Risposta(CSV, lunghezza=len(CSV) + 100) for _ in range(3)))
    with pytest.raises(ErroreDownload, match="troncat"):
        scarica("https://x/a.csv", apri=apri, dormi=lambda s: None)


def test_senza_content_length_accettata():
    apri = Apri(Risposta(CSV, lunghezza=None))
    assert scarica("https://x/a.csv", apri=apri, dormi=lambda s: None) == CSV


def test_risposta_vuota_rifiutata():
    apri = Apri(*(Risposta(b"") for _ in range(3)))
    with pytest.raises(ErroreDownload, match="vuot"):
        scarica("https://x/a.csv", apri=apri, dormi=lambda s: None)


def test_indice_precedente_somma_n_e_legge_prezzi_del():
    corpo = (b'{"schema":1,"prezziDel":"2026-09-29T08:00:00+02:00",'
             b'"province":[{"sigla":"BA","n":400},{"sigla":"BR","n":180}]}')
    prec = indice_precedente("https://x/index.json", apri=Apri(Risposta(corpo, tipo="application/json")))
    assert prec.n == 580
    assert prec.prezzi_del == "2026-09-29T08:00:00+02:00"


def test_indice_precedente_senza_prezzi_del():
    corpo = b'{"schema":1,"province":[{"sigla":"BA","n":400}]}'
    prec = indice_precedente("https://x/index.json", apri=Apri(Risposta(corpo, tipo="application/json")))
    assert (prec.n, prec.prezzi_del) == (400, None)


@pytest.mark.parametrize("esito", [
    urllib.error.HTTPError("https://x", 404, "Not Found", {}, None),
    urllib.error.URLError("giu"),
    Risposta(b"non json", tipo="application/json"),
    Risposta(b'{"schema":1}', tipo="application/json"),
])
def test_indice_precedente_irraggiungibile_o_rotto_da_none(esito):
    assert indice_precedente("https://x/index.json", apri=Apri(esito)) is None


def test_indice_precedente_senza_url_da_none():
    assert indice_precedente(None) is None
