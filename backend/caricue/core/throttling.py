"""Throttles for public (unauthenticated) and authentication endpoints.

Uses DRF's cache-backed throttling. With the default local-memory cache this
is per-process; the production compose file runs a single Gunicorn service so
the limits hold. Swapping in a shared cache backend is the documented
extension point for multi-instance deployments.
"""

from rest_framework.throttling import AnonRateThrottle


class PublicLookupThrottle(AnonRateThrottle):
    """Guards short-code lookups, which are the only guessable identifier."""

    scope = "public_lookup"


class PublicJoinThrottle(AnonRateThrottle):
    scope = "public_join"


class PublicSubmitThrottle(AnonRateThrottle):
    scope = "public_submit"


class AuthAttemptThrottle(AnonRateThrottle):
    """Slows down credential stuffing against login/register."""

    scope = "auth_attempt"
