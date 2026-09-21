# CariCue API image.
#
# Single stage on purpose: the only build inputs are wheels, and psycopg ships
# a binary wheel, so a builder stage would add complexity without shrinking
# the result meaningfully.
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DJANGO_SETTINGS_MODULE=caricue.settings \
    DJANGO_STATIC_ROOT=/var/www/caricue/static

WORKDIR /app

# libpq is needed at runtime by psycopg; curl backs the container health check.
RUN apt-get update \
    && apt-get install --no-install-recommends -y libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY . .

# Static files are collected into a volume-friendly path that Nginx can also
# read in the production compose file.
RUN mkdir -p "$DJANGO_STATIC_ROOT" \
    && addgroup --system --gid 1001 caricue \
    && adduser --system --uid 1001 --gid 1001 caricue \
    && chown -R caricue:caricue /app "$DJANGO_STATIC_ROOT"

COPY --chown=caricue:caricue entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

USER caricue

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/api/health/ || exit 1

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["gunicorn", "caricue.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "3", \
     "--timeout", "60", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
