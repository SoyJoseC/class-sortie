"""Operational endpoints."""

from __future__ import annotations

import django
from django.conf import settings
from django.db import connection
from rest_framework import status
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def health(request: Request) -> Response:
    """Liveness + database readiness probe.

    Used by Docker health checks and by the Nginx upstream check. Returns 503
    when the database is unreachable so orchestrators can act on it.
    """
    database_ok = True
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:  # noqa: BLE001 - health check must never raise
        database_ok = False

    payload = {
        "status": "ok" if database_ok else "degraded",
        "service": "caricue-api",
        "database": "ok" if database_ok else "unavailable",
        "django": django.get_version(),
        "debug": settings.DEBUG,
    }
    http_status = (
        status.HTTP_200_OK if database_ok else status.HTTP_503_SERVICE_UNAVAILABLE
    )
    return Response(payload, status=http_status)


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def client_config(request: Request) -> Response:
    """Non-secret runtime configuration the SPA needs."""
    return Response(
        {
            "public_base_url": settings.PUBLIC_BASE_URL,
            "dashboard_poll_seconds": settings.CARICUE["DASHBOARD_POLL_SECONDS"],
            "min_questions": settings.CARICUE["MIN_QUESTIONS_PER_ACTIVITY"],
            "max_questions": settings.CARICUE["MAX_QUESTIONS_PER_ACTIVITY"],
            "max_choices": settings.CARICUE["MAX_CHOICES_PER_QUESTION"],
            "ai_suggestions_enabled": bool(settings.INSIGHT_LLM_API_KEY),
        }
    )
