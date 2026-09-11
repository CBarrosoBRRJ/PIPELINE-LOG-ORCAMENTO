#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
mkdir -p runtime/backups
umask 077
TARGET="runtime/backups/pipeline_$(date -u +%Y%m%dT%H%M%SZ).dump"
SERVICES="$(docker compose --profile backup config --services)"
if [[ "$SERVICES" == *backup* ]]; then
  docker compose --profile backup run --rm -T backup >"$TARGET.partial"
else
  docker compose exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' >"$TARGET.partial"
fi
mv -- "$TARGET.partial" "$TARGET"
printf 'Backup criado: %s\n' "$TARGET"
