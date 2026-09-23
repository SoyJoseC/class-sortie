"""Google OAuth flows for teachers and students."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model

from caricue.accounts.google_oauth import GoogleProfile
from caricue.accounts.models import StudentAccount
from caricue.accounts.student_account import STUDENT_SESSION_KEY

pytestmark = pytest.mark.django_db

Teacher = get_user_model()


@pytest.fixture
def oauth_settings(settings):
    settings.GOOGLE_OAUTH_CLIENT_ID = "test-client-id"
    settings.GOOGLE_OAUTH_CLIENT_SECRET = "test-client-secret"
    settings.GOOGLE_OAUTH_REDIRECT_URI = "http://testserver/api/auth/google/callback/"
    settings.OAUTH_ALLOWED_EMAIL_DOMAINS = ["example.edu"]
    return settings


def test_google_login_redirects_to_google(api, oauth_settings):
    response = api.get("/api/auth/google/login/?role=teacher&next=/app")
    assert response.status_code == 302
    assert "accounts.google.com" in response.url
    assert "oauth_state" in api.session


@patch("caricue.accounts.views.exchange_code")
def test_teacher_google_callback_creates_teacher(mock_exchange, api, oauth_settings):
    mock_exchange.return_value = GoogleProfile(
        sub="google-sub-1",
        email="newteacher@example.edu",
        full_name="New Teacher",
    )
    session = api.session
    session["oauth_state"] = "fixed-state"
    session["oauth_role"] = "teacher"
    session["oauth_next"] = "/app"
    session.save()

    response = api.get("/api/auth/google/callback/?code=abc&state=fixed-state")

    assert response.status_code == 302
    assert response.url == "/app"
    teacher = Teacher.objects.get(email="newteacher@example.edu")
    assert teacher.google_sub == "google-sub-1"
    assert teacher.full_name == "New Teacher"


@patch("caricue.accounts.views.exchange_code")
def test_teacher_google_callback_rejects_other_domain(mock_exchange, api, oauth_settings):
    mock_exchange.return_value = GoogleProfile(
        sub="google-sub-2",
        email="person@gmail.com",
        full_name="Outside Domain",
    )
    session = api.session
    session["oauth_state"] = "fixed-state"
    session["oauth_role"] = "teacher"
    session["oauth_next"] = "/login"
    session.save()

    response = api.get("/api/auth/google/callback/?code=abc&state=fixed-state")

    assert response.status_code == 302
    assert "oauth_error=domain_not_allowed" in response.url
    assert not Teacher.objects.filter(email="person@gmail.com").exists()


@patch("caricue.accounts.views.exchange_code")
def test_student_google_callback_sets_student_session(mock_exchange, api, oauth_settings):
    mock_exchange.return_value = GoogleProfile(
        sub="student-sub-1",
        email="student@example.edu",
        full_name="Student One",
    )
    session = api.session
    session["oauth_state"] = "student-state"
    session["oauth_role"] = "student"
    session["oauth_next"] = "/join/class/token123"
    session.save()

    response = api.get("/api/auth/google/callback/?code=abc&state=student-state")

    assert response.status_code == 302
    assert response.url == "/join/class/token123"
    assert STUDENT_SESSION_KEY in api.session
    account = StudentAccount.objects.get(email="student@example.edu")
    assert account.full_name == "Student One"


def test_student_me_requires_session(api):
    response = api.get("/api/auth/student/me/")
    assert response.status_code == 401


def test_google_account_session_join(
    api, activity, classroom, teacher, make_student, make_activity
):
    from caricue.classroom.models import Enrollment
    from caricue.live.models import IdentityMode
    from caricue.live.services import launch_session

    student = make_student(teacher, "Amara J", email="amara@example.edu")
    Enrollment.objects.create(classroom=classroom, student=student)

    session, error = launch_session(
        activity=activity, identity_mode=IdentityMode.GOOGLE_ACCOUNT
    )
    assert error == ""

    account = StudentAccount.objects.create(
        email="amara@example.edu",
        full_name="Amara J",
        google_sub="amara-sub",
    )
    session_client = api.session
    session_client[STUDENT_SESSION_KEY] = account.pk
    session_client.save()

    response = api.post(f"/api/public/sessions/{session.public_token}/join/", {})

    assert response.status_code == 201
    assert response.data["participant_token"]
    assert response.data["display_label"] == "Amara J"


def test_student_me_returns_profile(api, db):
    account = StudentAccount.objects.create(
        email="student@example.edu",
        full_name="Student One",
        google_sub="student-sub-1",
    )
    session = api.session
    session[STUDENT_SESSION_KEY] = account.pk
    session.save()

    response = api.get("/api/auth/student/me/")

    assert response.status_code == 200
    assert response.data["email"] == "student@example.edu"
