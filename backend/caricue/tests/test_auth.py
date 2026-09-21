"""Teacher authentication: registration, login, logout, current user, CSRF."""

from __future__ import annotations

import pytest
from django.urls import reverse

from caricue.accounts.models import Teacher

pytestmark = pytest.mark.django_db


def test_register_creates_teacher_and_signs_them_in(api):
    response = api.post(
        reverse("auth-register"),
        {
            "email": "New.Teacher@Example.edu",
            "full_name": "New Teacher",
            "school_name": "Coastal High",
            "password": "StrongPassphrase99",
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.data["email"] == "new.teacher@example.edu"
    assert "password" not in response.data
    assert Teacher.objects.filter(email="new.teacher@example.edu").exists()

    # Registration establishes the session, so the SPA does not need a
    # second round trip to log in.
    me = api.get(reverse("auth-me"))
    assert me.status_code == 200
    assert me.data["full_name"] == "New Teacher"


def test_register_rejects_weak_password(api):
    response = api.post(
        reverse("auth-register"),
        {"email": "weak@example.edu", "full_name": "Weak", "password": "password"},
        format="json",
    )
    assert response.status_code == 400
    assert "password" in response.data["errors"]
    assert not Teacher.objects.filter(email="weak@example.edu").exists()


def test_register_rejects_duplicate_email(api, teacher):
    response = api.post(
        reverse("auth-register"),
        {
            "email": teacher.email.upper(),
            "full_name": "Impostor",
            "password": "AnotherStrongPass1",
        },
        format="json",
    )
    assert response.status_code == 400
    assert Teacher.objects.filter(email=teacher.email).count() == 1


def test_login_succeeds_and_me_returns_profile(api, teacher):
    response = api.post(
        reverse("auth-login"),
        {"email": teacher.email, "password": "TestPassphrase123"},
        format="json",
    )
    assert response.status_code == 200
    assert response.data["email"] == teacher.email

    me = api.get(reverse("auth-me"))
    assert me.status_code == 200
    assert me.data["id"] == teacher.pk


def test_login_is_case_insensitive_on_email(api, teacher):
    response = api.post(
        reverse("auth-login"),
        {"email": teacher.email.upper(), "password": "TestPassphrase123"},
        format="json",
    )
    assert response.status_code == 200


def test_login_with_wrong_password_is_rejected(api, teacher):
    response = api.post(
        reverse("auth-login"),
        {"email": teacher.email, "password": "WrongPassword123"},
        format="json",
    )
    assert response.status_code == 400
    assert api.get(reverse("auth-me")).status_code == 403


def test_login_error_does_not_reveal_whether_the_account_exists(api, teacher):
    unknown = api.post(
        reverse("auth-login"),
        {"email": "nobody@example.edu", "password": "WrongPassword123"},
        format="json",
    )
    wrong_password = api.post(
        reverse("auth-login"),
        {"email": teacher.email, "password": "WrongPassword123"},
        format="json",
    )
    assert unknown.status_code == wrong_password.status_code == 400
    assert unknown.data["detail"] == wrong_password.data["detail"]


def test_logout_ends_the_session(api, teacher):
    """Logs in for real: `force_authenticate` bypasses sessions entirely, so it
    could not show that logout actually clears one."""
    api.post(
        reverse("auth-login"),
        {"email": teacher.email, "password": "TestPassphrase123"},
        format="json",
    )
    assert api.get(reverse("auth-me")).status_code == 200

    assert api.post(reverse("auth-logout")).status_code == 204
    assert api.get(reverse("auth-me")).status_code == 403


def test_me_requires_authentication(api):
    assert api.get(reverse("auth-me")).status_code == 403


def test_teacher_can_update_own_profile(auth_client, teacher):
    response = auth_client.patch(
        reverse("auth-me"),
        {"full_name": "Ms. A. Rowley", "school_name": "Northern Coast"},
        format="json",
    )
    assert response.status_code == 200
    teacher.refresh_from_db()
    assert teacher.full_name == "Ms. A. Rowley"


def test_email_cannot_be_changed_through_the_profile_endpoint(auth_client, teacher):
    original = teacher.email
    response = auth_client.patch(
        reverse("auth-me"), {"email": "hijack@example.edu"}, format="json"
    )
    assert response.status_code == 200
    teacher.refresh_from_db()
    assert teacher.email == original


def test_csrf_endpoint_sets_the_cookie(api):
    response = api.get(reverse("auth-csrf"))
    assert response.status_code == 200
    assert response.data["csrf_token"]
    assert "caricue_csrftoken" in response.cookies


def test_unsafe_request_without_csrf_token_is_blocked(client, teacher):
    """Session auth must be paired with CSRF enforcement.

    Uses Django's test client with `enforce_csrf_checks`, because DRF's
    `APIClient` exempts CSRF by default.
    """
    from django.test import Client

    csrf_client = Client(enforce_csrf_checks=True)
    assert csrf_client.login(email=teacher.email, password="TestPassphrase123")

    response = csrf_client.post(
        reverse("classroom-list"),
        data={"name": "No CSRF"},
        content_type="application/json",
    )
    assert response.status_code == 403


def test_session_cookie_is_httponly_and_samesite(api, teacher):
    api.post(
        reverse("auth-login"),
        {"email": teacher.email, "password": "TestPassphrase123"},
        format="json",
    )
    cookie = api.cookies["caricue_session"]
    assert cookie["httponly"]
    assert cookie["samesite"] == "Lax"
