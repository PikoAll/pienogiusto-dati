"""Unit tests for the tolerant MIMIT CSV parser (pure logic on in-memory bytes)."""
from datetime import date

import pytest

from pienogiusto_dati.parser import (
    FormatoNonValido,
    decodifica,
    parse_anagrafica,
    parse_prezzi,
)

HEAD_A = "idImpianto|Gestore|Bandiera|Tipo Impianto|Nome Impianto|Indirizzo|Comune|Provincia|Latitudine|Longitudine"
HEAD_P = "idImpianto|descCarburante|prezzo|isSelf|dtComu"


def anag(*rows: str, estrazione: str | None = "Estrazione del 2026-09-29") -> bytes:
    lines = ([estrazione] if estrazione else []) + [HEAD_A, *rows]
    return ("\n".join(lines) + "\n").encode("utf-8")


def prezzi(*rows: str, estrazione: str | None = "Estrazione del 2026-09-29") -> bytes:
    lines = ([estrazione] if estrazione else []) + [HEAD_P, *rows]
    return "\n".join(lines).encode("utf-8")


ROW = "1|GEST|Q8|Stradale|NOME|VIA ROMA 1|MONOPOLI|BA|40.95|17.30"


class TestDecodifica:
    def test_utf8(self):
        assert decodifica("FORLÌ".encode("utf-8")) == ("FORLÌ", "utf-8")

    def test_utf8_bom(self):
        assert decodifica("﻿abc".encode("utf-8")) == ("abc", "utf-8")

    def test_latin1_fallback(self):
        assert decodifica("FORLÌ".encode("cp1252")) == ("FORLÌ", "cp1252")


class TestCaratteriIllegibili:
    def test_righe_con_carattere_sostitutivo_contate(self):
        # 0x81 and 0x9d are invalid UTF-8 and undefined in cp1252: they become U+FFFD
        data = anag(ROW).rstrip(b"\n") + b"\n2|G\x81|Q8|Stradale|N\x9d|I|C|BA|40.9|17.3\n"
        r = parse_anagrafica(data)
        assert r.codifica == "cp1252"
        assert r.righe_con_sostituzioni == 1

    def test_carattere_sostitutivo_gia_nel_testo_utf8(self):
        r = parse_prezzi(prezzi("1|Gasolio\ufffd|1.6|1|28/09/2026 19:12:00"))
        assert r.righe_con_sostituzioni == 1

    def test_testo_pulito_zero(self):
        assert parse_anagrafica(anag(ROW)).righe_con_sostituzioni == 0


class TestAnagrafica:
    def test_riga_semplice(self):
        r = parse_anagrafica(anag(ROW))
        imp = r.impianti[1]
        assert (imp.nome, imp.band, imp.ind, imp.com, imp.prov) == ("NOME", "Q8", "VIA ROMA 1", "MONOPOLI", "BA")
        assert (imp.lat, imp.lon) == (40.95, 17.30)
        assert r.estrazione == date(2026, 9, 29)
        assert r.separatore == "|"
        assert r.righe == 1

    def test_senza_riga_estrazione(self):
        r = parse_anagrafica(anag(ROW, estrazione=None))
        assert r.estrazione is None
        assert 1 in r.impianti

    def test_separatore_virgola(self):
        data = ("Estrazione del 2026-09-29\n" + HEAD_A.replace("|", ",") + "\n"
                + ROW.replace("|", ",") + "\n").encode()
        r = parse_anagrafica(data)
        assert r.separatore == ","
        assert r.impianti[1].com == "MONOPOLI"

    def test_separatore_punto_e_virgola(self):
        data = (HEAD_A.replace("|", ";") + "\n" + ROW.replace("|", ";") + "\n").encode()
        assert parse_anagrafica(data).separatore == ";"

    def test_coordinate_con_virgola_decimale(self):
        r = parse_anagrafica(anag("1|G|Q8|Stradale|N|I|C|BA|40,95|17,30"))
        assert (r.impianti[1].lat, r.impianti[1].lon) == (40.95, 17.30)

    def test_coordinate_mancanti_restano_none(self):
        r = parse_anagrafica(anag("1|G|Q8|Stradale||VIA|C|BN||"))
        assert r.impianti[1].lat is None and r.impianti[1].lon is None

    def test_spazi_tab_e_virgolette_ripuliti(self):
        r = parse_anagrafica(anag('1|"IP SERVICES S.R.L."|Api-Ip|Stradale|19834\tMONTALLEGRO|  SS 115  KM 1  |C|AG|37.3|13.3'))
        imp = r.impianti[1]
        assert imp.nome == "19834 MONTALLEGRO"
        assert imp.ind == "SS 115 KM 1"

    def test_virgoletta_sbilanciata_non_fonde_le_righe(self):
        r = parse_anagrafica(anag('1|"MEGA SERVICE S.A.S.|Q8|Stradale|N|I|C|AG|37.2|13.9', ROW.replace("1|", "2|", 1)))
        assert set(r.impianti) == {1, 2}

    def test_separatore_nel_nome_recuperato(self):
        r = parse_anagrafica(anag("40820|STOIL|Pompe Bianche|Stradale|STOIL SIMPLE | gestori.prezzibenzina.it|STR. PROV.LE 82|ALESSANDRIA|AL|44.9|8.7"))
        imp = r.impianti[40820]
        assert imp.nome == "STOIL SIMPLE"
        assert imp.ind == "STR. PROV.LE 82"
        assert imp.band == "Pompe Bianche"

    def test_separatore_nel_gestore_e_nel_nome(self):
        r = parse_anagrafica(anag("54386|PRADELLI | gestori.prezzibenzina.it|Pompe Bianche|Stradale|PRADELLI - M | gestori.prezzibenzina.it|Via dei Martiri 255|ZOCCA|MO|44.3|11.0"))
        imp = r.impianti[54386]
        assert (imp.nome, imp.band, imp.ind, imp.com) == ("PRADELLI - M", "Pompe Bianche", "Via dei Martiri 255", "ZOCCA")

    def test_riga_corta_scartata_e_contata(self):
        r = parse_anagrafica(anag(ROW, "2|G|Q8|Stradale|N"))
        assert list(r.impianti) == [1]
        assert r.scarti["riga_malformata"] == 1

    def test_id_non_numerico_scartato(self):
        r = parse_anagrafica(anag(ROW.replace("1|", "X|", 1)))
        assert r.impianti == {} and r.scarti["id_non_valido"] == 1

    def test_provincia_non_valida_scartata(self):
        r = parse_anagrafica(anag(ROW.replace("|BA|", "|Bari|")))
        assert r.impianti == {} and r.scarti["provincia_non_valida"] == 1

    def test_id_duplicato_tiene_il_primo(self):
        r = parse_anagrafica(anag(ROW, ROW.replace("MONOPOLI", "BARI")))
        assert r.impianti[1].com == "MONOPOLI" and r.scarti["id_duplicato"] == 1

    def test_intestazioni_diverse_rifiutate(self):
        with pytest.raises(FormatoNonValido, match="intestazioni"):
            parse_anagrafica(anag(ROW).replace(b"Latitudine", b"Lat"))

    def test_html_rifiutato(self):
        with pytest.raises(FormatoNonValido, match="HTML"):
            parse_anagrafica(b"<!DOCTYPE html><html><body>errore</body></html>")

    def test_file_vuoto_rifiutato(self):
        with pytest.raises(FormatoNonValido):
            parse_anagrafica(b"")


class TestPrezzi:
    def test_riga_semplice(self):
        r = parse_prezzi(prezzi("1|Gasolio|1.679|1|28/09/2026 19:12:00"))
        (p,) = r.prezzi[1]
        assert (p.c, p.self, p.v, p.t) == ("Gasolio", True, 1.679, "2026-09-28T19:12:00")

    def test_prezzo_con_virgola_e_servito(self):
        (p,) = parse_prezzi(prezzi("1|GPL|0,849|0|28/09/2026 10:01:58")).prezzi[1]
        assert (p.v, p.self) == (0.849, False)

    def test_data_non_valida_scartata(self):
        r = parse_prezzi(prezzi("1|GPL|0.849|0|ieri"))
        assert r.prezzi == {} and r.scarti["data_non_valida"] == 1

    def test_self_non_valido_scartato(self):
        r = parse_prezzi(prezzi("1|GPL|0.849|forse|28/09/2026 10:01:58"))
        assert r.prezzi == {} and r.scarti["self_non_valido"] == 1

    def test_prezzo_non_numerico_scartato(self):
        r = parse_prezzi(prezzi("1|GPL|n.d.|0|28/09/2026 10:01:58"))
        assert r.prezzi == {} and r.scarti["prezzo_non_valido"] == 1

    def test_duplicato_tiene_il_piu_recente(self):
        r = parse_prezzi(prezzi("1|GPL|0.8|0|27/09/2026 10:00:00", "1|GPL|0.9|0|28/09/2026 10:00:00"))
        (p,) = r.prezzi[1]
        assert p.v == 0.9 and r.scarti["prezzo_duplicato"] == 1

    def test_estrazione_letta(self):
        assert parse_prezzi(prezzi("1|GPL|0.8|0|27/09/2026 10:00:00")).estrazione == date(2026, 9, 29)

    def test_ultima_comunicazione(self):
        r = parse_prezzi(prezzi("1|GPL|0.8|0|27/09/2026 10:00:00", "2|GPL|0.8|0|29/09/2026 08:03:30"))
        assert r.ultima_comunicazione.isoformat() == "2026-09-29T08:03:30"
