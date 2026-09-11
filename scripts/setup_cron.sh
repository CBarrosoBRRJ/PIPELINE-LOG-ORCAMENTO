#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
# Do not source .env: credentials may contain shell metacharacters.
SCHEDULE="$(docker compose --profile job run --rm --no-deps --entrypoint python pipeline -c 'from sls_orcamento_pdd.config import Settings; print(Settings().cron_schedule)')"
LINE="$SCHEDULE /bin/bash \"$ROOT/scripts/run_daily.sh\" # sls_orcamento_pdd"
{ crontab -l 2>/dev/null | sed '/# sls_orcamento_pdd$/d' || true; printf '%s\n' "$LINE"; } | crontab -
printf 'Agendamento instalado no timezone do servidor: %s\n' "$SCHEDULE"
