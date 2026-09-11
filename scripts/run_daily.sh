#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
mkdir -p logs runtime
exec 9>runtime/daily.lock
flock -n 9 || exit 0
docker compose --profile job run --rm pipeline daily >>logs/daily.log 2>&1
