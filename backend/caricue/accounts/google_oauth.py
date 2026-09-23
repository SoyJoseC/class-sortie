"""Google OAuth 2.0 for teachers and students (shared client, role in state)."""

from __future__ import annotations

import json
import secrets
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from django.conf import settings


class GoogleOAuthError(Exception):
    def __init__(self, message: str, code: str = "oauth_error") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


@dataclass
class GoogleProfile:
    sub: str
    email: str
    full_name: str


def _oauth_configured() -> bool:
    return bool(settings.GOOGLE_OAUTH_CLIENT_ID and settings.GOOGLE_OAUTH_CLIENT_SECRET)


def build_authorization_url(*, state: str) -> str:
    if not _oauth_configured():
        raise GoogleOAuthError(
            "Google sign-in is not configured.", "oauth_not_configured"
        )
    params = {
        "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    query = urllib.parse.urlencode(params)
    return f"https://accounts.google.com/o/oauth2/v2/auth?{query}"


def exchange_code(code: str) -> GoogleProfile:
    if not _oauth_configured():
        raise GoogleOAuthError(
            "Google sign-in is not configured.", "oauth_not_configured"
        )
    token_payload = urllib.parse.urlencode(
        {
            "code": code,
            "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
            "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
            "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI,
            "grant_type": "authorization_code",
        }
    ).encode()
    token_req = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=token_payload,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(token_req, timeout=15) as resp:  # noqa: S310
            token_data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        raise GoogleOAuthError("Google sign-in failed.", "oauth_exchange_failed") from exc

    access_token = token_data.get("access_token")
    if not access_token:
        raise GoogleOAuthError(
            "Google did not return an access token.", "oauth_exchange_failed"
        )

    user_req = urllib.request.Request(
        "https://www.googleapis.com/oauth2/v3/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    try:
        with urllib.request.urlopen(user_req, timeout=15) as resp:  # noqa: S310
            user = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        raise GoogleOAuthError(
            "Could not read your Google profile.", "oauth_profile_failed"
        ) from exc

    email = (user.get("email") or "").strip().lower()
    if not email or not user.get("email_verified"):
        raise GoogleOAuthError(
            "A verified Google email address is required.", "email_not_verified"
        )
    return GoogleProfile(
        sub=user.get("sub") or "",
        email=email,
        full_name=(user.get("name") or email.split("@")[0]).strip(),
    )


def email_domain_allowed(email: str) -> bool:
    domains = settings.OAUTH_ALLOWED_EMAIL_DOMAINS
    if not domains:
        return True
    if "@" not in email:
        return False
    domain = email.rsplit("@", 1)[1].lower()
    return domain in domains


def new_oauth_state() -> str:
    return secrets.token_urlsafe(32)
