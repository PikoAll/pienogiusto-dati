#!/usr/bin/env bash
# Entry point expected by the lotto-card PR gate; delegates to scripts/run-checks.sh
set -u

cd "$(dirname "$0")/../.." || exit 1
exec bash scripts/run-checks.sh "$@"
