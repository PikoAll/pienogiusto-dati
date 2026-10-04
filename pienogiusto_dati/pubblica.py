"""Entry point: download -> parse -> join -> gates -> site/ (index.json, p/<SIGLA>.json.gz, comuni.json.gz, report.json).

Exit codes: 0 published or nothing new, 1 a gate failed (header and stale data included),
2 download/usage error. Nothing is written unless every gate passes (FAIL-CLOSED).
Under GitHub Actions it appends `nuovo=true|false` to $GITHUB_OUTPUT: deploy only when true.

    python -m pienogiusto_dati.pubblica --uscita site --indice-precedente https://<owner>.github.io/pienogiusto-dati/index.json
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
import time
from datetime import datetime, time as dtime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from . import cancelli
from .comuni import elenco_comuni
from .parser import FormatoNonValido, parse_anagrafica, parse_prezzi
from .scarica import (URL_ANAGRAFICA, URL_PREZZI, ErroreDownload, IndicePrecedente, indice_precedente,
                      scarica)
from .unisci import unisci

SCHEMA = 1
ROMA = ZoneInfo("Europe/Rome")
LEGGIMI = """PienoGiusto - dati carburanti per provincia

Fonte: Ministero delle Imprese e del Made in Italy (MIMIT), dataset
"Carburanti - Prezzi praticati e anagrafica degli impianti",
https://www.mimit.gov.it/it/open-data/elenco-dataset/carburanti-prezzi-praticati-e-anagrafica-degli-impianti
Licenza: Italian Open Data License v2.0 (IODL 2.0), https://www.dati.gov.it/iodl/2.0/
I dati sono stati filtrati, uniti e riformattati; il MIMIT non e' responsabile di queste elaborazioni.
Formato: docs/CONTRATTO.md nel repo pienogiusto-dati.
"""


def _leggi(sorgente: str) -> bytes:
    if sorgente.startswith(("http://", "https://")):
        return scarica(sorgente)
    return Path(sorgente).read_bytes()


def _json(dati) -> bytes:
    return json.dumps(dati, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _prezzi_del(prezzi) -> str:
    giorno = prezzi.estrazione or (prezzi.ultima_comunicazione and prezzi.ultima_comunicazione.date())
    if not giorno:
        raise FormatoNonValido("impossibile stabilire la data dei prezzi")
    return datetime.combine(giorno, dtime(8, 0), tzinfo=ROMA).isoformat()


def costruisci(dati_anagrafica: bytes, dati_prezzi: bytes, precedente: IndicePrecedente | None,
               adesso: datetime):
    """Pure part of the pipeline: returns (files to write, report, is it new). Raises on failed gates."""
    anag = parse_anagrafica(dati_anagrafica)
    prezzi = parse_prezzi(dati_prezzi)
    unione = unisci(anag, prezzi)
    comuni = elenco_comuni(unione)
    esiti = cancelli.verifica_cancelli(anag, prezzi, unione, comuni, precedente and precedente.n)
    prezzi_del = _prezzi_del(prezzi)
    nuovo = cancelli.valuta_novita(prezzi_del, precedente and precedente.prezzi_del, adesso)

    file: dict[str, bytes] = {}
    province = []
    for sigla in sorted(unione.province):
        nome = f"p/{sigla}.json.gz"
        file[nome] = gzip.compress(_json({"schema": SCHEMA, "impianti": unione.province[sigla]}),
                                   compresslevel=9, mtime=0)
        province.append({"sigla": sigla, "file": nome, "n": len(unione.province[sigla]),
                         "bbox": unione.bbox(sigla)})
    file["comuni.json.gz"] = gzip.compress(_json({"schema": SCHEMA, "comuni": comuni}), compresslevel=9, mtime=0)
    pubblicato = adesso.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    index = {"schema": SCHEMA, "pubblicato": pubblicato, "prezziDel": prezzi_del, "province": province,
             "comuni": "comuni.json.gz"}
    file["index.json"] = _json(index)
    file["LEGGIMI.txt"] = LEGGIMI.encode("utf-8")

    scarti = dict(sorted({**anag.scarti, **prezzi.scarti, **unione.scarti}.items()))
    report = {
        "pubblicato": pubblicato,
        "prezziDel": index["prezziDel"],
        "sorgenti": {
            nome: {"byte": len(b), "righe": r.righe, "codifica": r.codifica, "separatore": r.separatore,
                   "estrazione": r.estrazione.isoformat() if r.estrazione else None}
            for nome, b, r in (("anagrafica", dati_anagrafica, anag), ("prezzi", dati_prezzi, prezzi))
        },
        "impianti_anagrafica": unione.anagrafica,
        "impianti_pubblicati": unione.pubblicati,
        "impianti_precedenti": precedente and precedente.n,
        "province": len(province),
        "comuni": len(comuni),
        "scarti": scarti,
        "cancelli": {e.nome: e.come_dict() for e in esiti},
        "byte_pubblicati": sum(len(v) for k, v in file.items() if k.startswith("p/")),
        "byte_comuni": len(file["comuni.json.gz"]),
    }
    return file, report, nuovo


def scrivi(uscita: Path, file: dict[str, bytes], report: dict) -> None:
    """Write into a sibling temp dir, then rename: site/ appears complete or not at all."""
    temp = uscita.with_name(uscita.name + ".in-corso")
    (temp / "p").mkdir(parents=True)
    for nome, dati in file.items():
        (temp / nome).write_bytes(dati)
    (temp / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.rename(temp, uscita)


def _output_workflow(nuovo: bool) -> None:
    percorso = os.environ.get("GITHUB_OUTPUT")
    if percorso:
        with open(percorso, "a", encoding="utf-8") as f:
            f.write(f"nuovo={'true' if nuovo else 'false'}\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="pienogiusto_dati.pubblica", description=__doc__.splitlines()[0])
    ap.add_argument("--anagrafica", default=URL_ANAGRAFICA, help="URL or local path")
    ap.add_argument("--prezzi", default=URL_PREZZI, help="URL or local path")
    ap.add_argument("--uscita", default="site", type=Path, help="output dir, must not exist")
    ap.add_argument("--indice-precedente", default=None, help="URL of the published index.json")
    ap.add_argument("--adesso", default=None, help="ISO timestamp for 'pubblicato' (tests)")
    a = ap.parse_args(argv)

    inizio = time.monotonic()
    for d in (a.uscita, a.uscita.with_name(a.uscita.name + ".in-corso")):
        if d.exists():
            print(f"ERRORE: {d} esiste gia': rinominala o scegli un'altra --uscita", file=sys.stderr)
            return 2
    adesso = datetime.fromisoformat(a.adesso) if a.adesso else datetime.now(timezone.utc)
    try:
        dati_a = _leggi(a.anagrafica)
        dati_p = _leggi(a.prezzi)
        precedente = indice_precedente(a.indice_precedente)
        file, report, nuovo = costruisci(dati_a, dati_p, precedente, adesso)
    except FormatoNonValido as e:
        print(f"CANCELLO FALLITO intestazioni/formato: {e}", file=sys.stderr)
        return 1
    except cancelli.CancelloFallito as e:
        print(f"CANCELLO FALLITO: {e}", file=sys.stderr)
        print(json.dumps({x.nome: x.come_dict() for x in e.esiti}, indent=2), file=sys.stderr)
        return 1
    except (ErroreDownload, OSError) as e:
        print(f"ERRORE download/lettura: {e}", file=sys.stderr)
        return 2
    if not nuovo:
        print(f"Niente di nuovo: prezziDel {report['prezziDel']} gia' pubblicato, non ripubblico.")
        _output_workflow(False)
        return 0
    report["durata_s"] = round(time.monotonic() - inizio, 2)
    a.uscita.parent.mkdir(parents=True, exist_ok=True)
    scrivi(a.uscita, file, report)
    print(json.dumps({k: report[k] for k in ("prezziDel", "impianti_pubblicati", "province",
                                             "byte_pubblicati", "durata_s")}))
    _output_workflow(True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
