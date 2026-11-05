"""Post-publication check: the public index.json must match what was just published.

The URL is always passed in by the caller (never hardcoded here). The check passes only
if the download answers HTTP 200 with a JSON object whose `pubblicato` equals the local one
and whose number of provinces equals the local one.

CLI: python -m pienogiusto_dati.verifica_pubblico --url URL --atteso site/index.json
Exit codes: 0 ok, 1 check failed, 2 usage or local file error.
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass(frozen=True)
class Esito:
    ok: bool
    motivo: str  # empty when ok
    tentativi: int  # attempts used


def _prova(url: str, atteso: dict, timeout: float) -> str:
    """Single attempt; returns "" when fine, else the reason of the failure."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as risposta:
            stato = risposta.status
            corpo = risposta.read()
    except urllib.error.HTTPError as e:
        return f"HTTP {e.code}"
    except (urllib.error.URLError, OSError) as e:
        return f"errore di rete: {getattr(e, 'reason', e)}"
    if stato != 200:
        return f"HTTP {stato}"
    try:
        dati = json.loads(corpo.decode("utf-8"))
    except ValueError as e:  # includes UnicodeDecodeError and JSONDecodeError
        return f"JSON non valido: {e}"
    if not isinstance(dati, dict):
        return "JSON non valido: non e' un oggetto"
    if dati.get("pubblicato") != atteso["pubblicato"]:
        return f"data vecchia: pubblicato {dati.get('pubblicato')}, atteso {atteso['pubblicato']}"
    province = dati.get("province")
    n = len(province) if isinstance(province, list) else 0
    if n != len(atteso["province"]):
        return f"province {n}, attese {len(atteso['province'])}"
    return ""


def verifica(url: str, atteso: dict, *, tentativi: int = 3, attesa: float = 30,
             timeout: float = 20, dormi=time.sleep) -> Esito:
    """Download `url` up to `tentativi` times, sleeping `attesa` s between attempts."""
    motivo = ""
    usati = 0
    for i in range(max(1, tentativi)):
        if i:
            dormi(attesa)
        usati = i + 1
        motivo = _prova(url, atteso, timeout)
        if not motivo:
            break
    return Esito(ok=not motivo, motivo=motivo, tentativi=usati)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="verifica_pubblico")
    parser.add_argument("--url", required=True)
    parser.add_argument("--atteso", required=True, help="local index.json just published")
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return 2
    try:
        with open(args.atteso, encoding="utf-8") as f:
            atteso = json.load(f)
        atteso["pubblicato"], len(atteso["province"])
    except (OSError, ValueError, KeyError, TypeError) as e:
        print(f"file atteso non utilizzabile: {e}", file=sys.stderr)
        return 2
    esito = verifica(args.url, atteso)
    if esito.ok:
        print("verifica-ok")
        return 0
    print(f"verifica-fallita: {esito.motivo}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
