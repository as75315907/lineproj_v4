#!/usr/bin/env bash

set -euo pipefail

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "DATABASE_URL is required"
  exit 1
fi

mkdir -p data/backups
timestamp="$(date +%Y%m%d-%H%M%S)"
pg_dump "$DATABASE_URL" > "data/backups/lineproj-${timestamp}.sql"
echo "Backup written to data/backups/lineproj-${timestamp}.sql"
