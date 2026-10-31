#!/usr/bin/env bash
# Single entry point for the repo checks, in the format read by the lotto-card gate
# (esito-run-checks.py, contract "pytest"): a "=== pytest ===" section and a final line.
#   bash scripts/run-checks.sh [--veloce | --completo]    (both profiles run the same suite)
set -u

PROFILO="--completo"
case "${1:-}" in
  --veloce|--completo) PROFILO="$1" ;;
  "") ;;
  *) echo "uso: $0 [--veloce|--completo]" >&2; exit 2 ;;
esac

cd "$(dirname "$0")/.." || exit 1

echo "=== pytest ==="
if ! python3 -m pytest -q -p no:cacheprovider; then
  echo "✗ ROSSO: 'pytest' (profilo $PROFILO)"
  exit 1
fi

echo
echo "TUTTI I CONTROLLI SONO VERDI (profilo $PROFILO)."
