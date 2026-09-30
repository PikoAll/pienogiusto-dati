"""Regression tests on the file formats MIMIT has published (fixtures in tests/fixtures/).

Each case is a real way the input has been, or can be, different:
old comma format, new pipe format, with and without the "Estrazione" line,
truncated file, HTML error page instead of CSV, cp1252 encoding with CRLF.
"""
import pytest

from pienogiusto_dati.parser import FormatoNonValido, parse_anagrafica, parse_prezzi


def test_formato_nuovo_pipe_reale(fixture_bytes):
    a = parse_anagrafica(fixture_bytes("anagrafica_reale.csv"))
    p = parse_prezzi(fixture_bytes("prezzi_reale.csv"))
    assert a.separatore == p.separatore == "|"
    assert a.estrazione.isoformat() == p.estrazione.isoformat() == "2026-09-29"
    assert a.righe == 163 and len(a.impianti) == 163 and not a.scarti
    assert p.righe == 636 and not p.scarti


def test_formato_vecchio_virgola(fixture_bytes):
    a = parse_anagrafica(fixture_bytes("anagrafica_virgola.csv"))
    p = parse_prezzi(fixture_bytes("prezzi_virgola.csv"))
    assert a.separatore == p.separatore == ","
    assert len(a.impianti) == 20 and not a.scarti
    assert p.estrazione is None and p.prezzi and not p.scarti


def test_senza_riga_estrazione(fixture_bytes):
    a = parse_anagrafica(fixture_bytes("anagrafica_senza_estrazione.csv"))
    assert a.estrazione is None and len(a.impianti) == 20


def test_file_troncato_ultima_riga_scartata(fixture_bytes):
    a = parse_anagrafica(fixture_bytes("anagrafica_troncata.csv"))
    assert a.scarti["riga_malformata"] + a.scarti["provincia_non_valida"] == 1
    p = parse_prezzi(fixture_bytes("prezzi_troncato.csv"))
    assert sum(p.scarti.values()) <= 1


def test_file_troncato_prima_delle_intestazioni():
    with pytest.raises(FormatoNonValido):
        parse_anagrafica(b"Estrazione del 2026-09-29\nidImpianto|Gestore|Band")


def test_pagina_html(fixture_bytes):
    with pytest.raises(FormatoNonValido, match="HTML"):
        parse_anagrafica(fixture_bytes("pagina_errore.html"))
    with pytest.raises(FormatoNonValido, match="HTML"):
        parse_prezzi(fixture_bytes("pagina_errore.html"))


def test_codifica_latin1_con_crlf(fixture_bytes):
    a = parse_anagrafica(fixture_bytes("anagrafica_latin1.csv"))
    assert a.codifica == "cp1252"
    imp = a.impianti[99901]
    assert (imp.com, imp.ind, imp.lon) == ("FORLÌ", "VIA GIOSUÈ CARDUCCI 1", 12.04)
