"""Test settings.

Sets environment defaults and then re-exports the real settings unchanged, so
the suite exercises production configuration rather than a parallel copy.

`setdefault` means CI can still pin any of these from the outside; in
particular, exporting ``DJANGO_DB_ENGINE=postgres`` runs the same tests
against PostgreSQL.
"""

import os

os.environ.setdefault("DJANGO_DEBUG", "true")
os.environ.setdefault("DJANGO_DB_ENGINE", "sqlite")
os.environ.setdefault("DJANGO_SQLITE_PATH", ":memory:")
os.environ.setdefault("PUBLIC_BASE_URL", "http://testserver")

from .settings import *

# Fast, deterministic hashing: these tests assert on behaviour, not on the
# cost factor of the production hasher.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Throttling is exercised by dedicated tests that clear this cache; give it a
# named, isolated backend so unrelated tests never trip a rate limit.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "caricue-tests",
    }
}
