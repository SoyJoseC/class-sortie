"""Tiny environment-variable helpers.

Kept dependency-free on purpose: settings are the only consumer and the
parsing rules need to be obvious to anyone deploying CariCue.
"""

from __future__ import annotations

import os

TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}


class ImproperlyConfigured(Exception):
    """Raised when a required environment variable is missing or unusable."""


def env_str(name: str, default: str | None = None, *, required: bool = False) -> str:
    value = os.environ.get(name)
    if value is None or value == "":
        if required:
            raise ImproperlyConfigured(f"Environment variable {name} is required.")
        return default if default is not None else ""
    return value


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    normalized = raw.strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    raise ImproperlyConfigured(
        f"Environment variable {name}={raw!r} is not a valid boolean. "
        f"Use one of {sorted(TRUE_VALUES | FALSE_VALUES)}."
    )


def env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ImproperlyConfigured(
            f"Environment variable {name}={raw!r} is not a valid integer."
        ) from exc


def env_list(name: str, default: list[str] | None = None) -> list[str]:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return list(default or [])
    return [item.strip() for item in raw.split(",") if item.strip()]
