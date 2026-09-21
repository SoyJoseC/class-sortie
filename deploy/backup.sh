#!/bin/sh
# Dumps the CariCue database to deploy/backups/.
#
#   ./deploy/backup.sh
#
# Uses the custom pg_dump format so restores can be parallelised and single
# tables can be pulled out if needed. Dumps contain student names: keep them
# encrypted at rest and out of version control (.gitignore already excludes
# this directory).
set -eu

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
BACKUP_DIR="${BACKUP_DIR:-./deploy/backups}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"

mkdir -p "$BACKUP_DIR"

# `--env-file .env` keeps POSTGRES_* consistent with the running stack.
docker compose -f "$COMPOSE_FILE" exec -T db \
    sh -c 'pg_dump --format=custom --no-owner --no-privileges \
        --username "$POSTGRES_USER" "$POSTGRES_DB"' \
    > "${BACKUP_DIR}/caricue-${STAMP}.dump"

echo "Wrote ${BACKUP_DIR}/caricue-${STAMP}.dump"

# Keep the 14 most recent dumps.
ls -1t "${BACKUP_DIR}"/caricue-*.dump 2>/dev/null | tail -n +15 | while read -r old; do
    echo "Removing old backup ${old}"
    rm -f "$old"
done
