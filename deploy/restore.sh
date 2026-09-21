#!/bin/sh
# Restores a CariCue dump produced by deploy/backup.sh.
#
#   ./deploy/restore.sh deploy/backups/caricue-20260304T101500Z.dump
#
# Destructive: `--clean` drops the existing objects first. Stop the API so no
# writes land mid-restore, then run migrations afterwards in case the dump
# predates the current code.
set -eu

DUMP="${1:-}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"

if [ -z "$DUMP" ] || [ ! -f "$DUMP" ]; then
    echo "Usage: $0 <path-to-dump>" >&2
    exit 2
fi

printf 'This will overwrite the current database from %s. Continue? [y/N] ' "$DUMP"
read -r reply
case "$reply" in
    y | Y) ;;
    *)
        echo 'Aborted.'
        exit 1
        ;;
esac

docker compose -f "$COMPOSE_FILE" stop api

docker compose -f "$COMPOSE_FILE" exec -T db \
    sh -c 'pg_restore --clean --if-exists --no-owner --no-privileges \
        --username "$POSTGRES_USER" --dbname "$POSTGRES_DB"' \
    < "$DUMP"

docker compose -f "$COMPOSE_FILE" start api

echo 'Restore complete. The API applies any outstanding migrations on start.'
