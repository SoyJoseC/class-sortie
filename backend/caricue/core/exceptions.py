"""Error handling that keeps responses safe and uniform.

Every API error is serialised as ``{"detail": str, "code": str, "errors": {}}``
so the SPA has one shape to handle, and unexpected exceptions never leak
tracebacks or database internals to a caller.
"""

from __future__ import annotations

import logging
from typing import Any

from django.core.exceptions import PermissionDenied
from django.db import IntegrityError
from django.http import Http404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger("caricue.api")

GENERIC_SERVER_ERROR = "Something went wrong. Please try again."


def safe_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    if isinstance(exc, IntegrityError):
        # Constraint violations are expected (duplicate submissions, duplicate
        # roster rows). Report a conflict without echoing the SQL.
        logger.info("Integrity error on %s: %s", context.get("view"), exc)
        return Response(
            {
                "detail": "That record conflicts with existing data.",
                "code": "conflict",
                "errors": {},
            },
            status=status.HTTP_409_CONFLICT,
        )

    response = exception_handler(exc, context)

    if response is None:
        logger.exception("Unhandled exception in %s", context.get("view"))
        return Response(
            {"detail": GENERIC_SERVER_ERROR, "code": "server_error", "errors": {}},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    if isinstance(exc, Http404 | PermissionDenied):
        detail = getattr(response, "data", {}).get("detail", "Not found.")
        response.data = {
            "detail": str(detail),
            "code": "not_found" if isinstance(exc, Http404) else "permission_denied",
            "errors": {},
        }
        return response

    data = response.data
    if isinstance(data, dict) and "detail" in data and len(data) == 1:
        response.data = {
            "detail": str(data["detail"]),
            "code": getattr(exc, "default_code", "error"),
            "errors": {},
        }
    elif isinstance(data, dict):
        response.data = {
            "detail": _first_message(data),
            "code": "invalid",
            "errors": data,
        }
    elif isinstance(data, list):
        response.data = {
            "detail": _first_message({"non_field_errors": data}),
            "code": "invalid",
            "errors": {"non_field_errors": data},
        }
    return response


def _first_message(errors: dict[str, Any]) -> str:
    for value in errors.values():
        if isinstance(value, list | tuple) and value:
            first = value[0]
            if isinstance(first, dict):
                nested = _first_message(first)
                if nested:
                    return nested
                continue
            return str(first)
        if isinstance(value, dict):
            nested = _first_message(value)
            if nested:
                return nested
        elif value:
            return str(value)
    return "The submitted data was not valid."
