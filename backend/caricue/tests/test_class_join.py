"""Class QR self-enrollment."""

from __future__ import annotations

import pytest

from caricue.accounts.models import StudentAccount
from caricue.accounts.student_account import STUDENT_SESSION_KEY
from caricue.classroom.models import Enrollment, Student

pytestmark = pytest.mark.django_db


def test_public_class_detail(api, classroom):
    response = api.get(f"/api/public/classes/{classroom.invite_token}/")

    assert response.status_code == 200
    assert response.data["name"] == classroom.name
    assert response.data["teacher_name"] == classroom.teacher.full_name
    assert "roster" not in str(response.data).lower()


def test_public_class_join_requires_student_session(api, classroom):
    classroom.self_enrollment_enabled = True
    classroom.save(update_fields=["self_enrollment_enabled"])

    response = api.post(f"/api/public/classes/{classroom.invite_token}/join/")

    assert response.status_code == 401
    assert response.data["code"] == "google_sign_in_required"


def test_public_class_join_creates_roster_row(api, classroom):
    classroom.self_enrollment_enabled = True
    classroom.save(update_fields=["self_enrollment_enabled"])

    account = StudentAccount.objects.create(
        email="newstudent@example.edu",
        full_name="New Student",
        google_sub="sub-new",
    )
    session = api.session
    session[STUDENT_SESSION_KEY] = account.pk
    session.save()

    response = api.post(f"/api/public/classes/{classroom.invite_token}/join/")

    assert response.status_code == 201
    student = Student.objects.get(email="newstudent@example.edu")
    assert student.display_name == "New Student"
    assert Enrollment.objects.filter(
        classroom=classroom, student=student, is_active=True
    ).exists()


def test_public_class_join_idempotent(api, classroom, make_student, teacher):
    classroom.self_enrollment_enabled = True
    classroom.save(update_fields=["self_enrollment_enabled"])

    make_student(teacher, "Existing", email="existing@example.edu")
    account = StudentAccount.objects.create(
        email="existing@example.edu",
        full_name="Existing Student",
        google_sub="sub-existing",
    )
    session = api.session
    session[STUDENT_SESSION_KEY] = account.pk
    session.save()

    first = api.post(f"/api/public/classes/{classroom.invite_token}/join/")
    second = api.post(f"/api/public/classes/{classroom.invite_token}/join/")

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.data["already_enrolled"] is True


def test_public_class_join_rejects_when_disabled(api, classroom):
    classroom.self_enrollment_enabled = False
    classroom.save(update_fields=["self_enrollment_enabled"])

    account = StudentAccount.objects.create(
        email="student@example.edu",
        full_name="Student",
        google_sub="sub-1",
    )
    session = api.session
    session[STUDENT_SESSION_KEY] = account.pk
    session.save()

    response = api.post(f"/api/public/classes/{classroom.invite_token}/join/")

    assert response.status_code == 403
    assert response.data["code"] == "enrollment_disabled"
