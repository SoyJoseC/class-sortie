#!/bin/sh
# Waits for PostgreSQL, applies migrations, collects static files, then runs
# the given command. Idempotent, so it is safe on every container start.
set -eu

wait_for_database() {
    [ "${DJANGO_DB_ENGINE:-postgres}" = "sqlite" ] && return 0

    attempts=0
    max_attempts="${DB_WAIT_ATTEMPTS:-30}"
    until python -c "
import sys
import django
from django.conf import settings
django.setup()
from django.db import connections
try:
    connections['default'].ensure_connection()
except Exception as exc:  # noqa: BLE001 - startup probe, any failure means retry
    print(exc, file=sys.stderr)
    sys.exit(1)
"; do
        attempts=$((attempts + 1))
        if [ "$attempts" -ge "$max_attempts" ]; then
            echo "Database did not become available after ${max_attempts} attempts." >&2
            exit 1
        fi
        echo "Waiting for the database (${attempts}/${max_attempts})…"
        sleep 2
    done
}

wait_for_database

if [ "${DJANGO_MIGRATE_ON_START:-1}" = "1" ]; then
    echo "Applying migrations…"
    python manage.py migrate --noinput
fi

if [ "${DJANGO_COLLECTSTATIC_ON_START:-1}" = "1" ]; then
    echo "Collecting static files…"
    python manage.py collectstatic --noinput --clear
fi

if [ "${CARICUE_SEED_DEMO:-0}" = "1" ]; then
    echo "Seeding demonstration data…"
    python manage.py seed_demo
fi

exec "$@"
