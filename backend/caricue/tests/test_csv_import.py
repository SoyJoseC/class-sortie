"""CSV roster import."""

from __future__ import annotations

import io

import pytest
from django.urls import reverse

from caricue.classroom.csv_import import SAMPLE_CSV
from caricue.classroom.models import Enrollment, Student

pytestmark = pytest.mark.django_db


def upload(client, classroom, content: str, filename: str = "roster.csv"):
    handle = io.BytesIO(content.encode("utf-8"))
    handle.name = filename
    return client.post(
        reverse("classroom-import-roster", args=[classroom.pk]),
        {"file": handle},
        format="multipart",
    )


def test_import_creates_students_and_enrolments(auth_client, classroom, teacher):
    response = upload(
        auth_client,
        classroom,
        "display_name,school_identifier,email\n"
        "Amara Joseph,STU-001,\n"
        "Devon Charles,STU-002,devon@example.edu\n",
    )

    assert response.status_code == 200
    assert response.data["created_students"] == 2
    assert response.data["created_enrollments"] == 2
    assert response.data["row_errors"] == []

    student = Student.objects.get(teacher=teacher, school_identifier="STU-002")
    assert student.email == "devon@example.edu"
    assert Enrollment.objects.filter(classroom=classroom).count() == 2


def test_only_display_name_is_required(auth_client, classroom):
    response = upload(auth_client, classroom, "display_name\nAmara Joseph\n")
    assert response.status_code == 200
    assert response.data["created_students"] == 1


def test_headers_are_matched_case_and_space_insensitively(auth_client, classroom):
    response = upload(
        auth_client,
        classroom,
        "Display Name,School-Identifier\nAmara Joseph,STU-001\n",
    )
    assert response.status_code == 200
    assert response.data["created_students"] == 1


def test_missing_required_column_is_rejected(auth_client, classroom):
    response = upload(auth_client, classroom, "name,email\nAmara,a@example.edu\n")
    assert response.status_code == 400
    assert "display_name" in response.data["detail"]
    assert Student.objects.count() == 0


def test_reimporting_the_same_file_is_idempotent(auth_client, classroom):
    content = "display_name,school_identifier\nAmara Joseph,STU-001\n"
    first = upload(auth_client, classroom, content)
    second = upload(auth_client, classroom, content)

    assert first.data["created_students"] == 1
    assert second.data["created_students"] == 0
    assert second.data["created_enrollments"] == 0
    assert Student.objects.count() == 1
    assert Enrollment.objects.filter(classroom=classroom).count() == 1


def test_reimport_updates_a_changed_display_name(auth_client, classroom, teacher):
    upload(auth_client, classroom, "display_name,school_identifier\nAmara J,STU-001\n")
    response = upload(
        auth_client, classroom, "display_name,school_identifier\nAmara Joseph,STU-001\n"
    )
    assert response.data["updated_students"] == 1
    assert Student.objects.get(school_identifier="STU-001").display_name == "Amara Joseph"


def test_invalid_rows_are_reported_and_valid_rows_still_import(auth_client, classroom):
    response = upload(
        auth_client,
        classroom,
        "display_name,school_identifier,email\n"
        "Amara Joseph,STU-001,\n"
        ",STU-002,\n"
        "Bad Email,STU-003,not-an-email\n"
        "Devon Charles,STU-004,\n",
    )

    assert response.status_code == 200
    assert response.data["created_students"] == 2
    errors = response.data["row_errors"]
    assert {err["line"] for err in errors} == {3, 4}
    assert Student.objects.count() == 2


def test_blank_rows_are_skipped_not_reported_as_errors(auth_client, classroom):
    response = upload(
        auth_client,
        classroom,
        "display_name,school_identifier\nAmara Joseph,STU-001\n,,\n\n",
    )
    assert response.status_code == 200
    assert response.data["created_students"] == 1
    assert response.data["row_errors"] == []
    assert response.data["skipped_rows"] >= 1


def test_duplicate_identifier_inside_one_file_is_reported_once(auth_client, classroom):
    response = upload(
        auth_client,
        classroom,
        "display_name,school_identifier\nAmara Joseph,STU-001\nAmara J,stu-001\n",
    )
    assert response.data["created_students"] == 1
    assert len(response.data["row_errors"]) == 1
    assert "Duplicate" in response.data["row_errors"][0]["message"]


def test_import_reactivates_a_dropped_enrolment(auth_client, classroom, teacher):
    content = "display_name,school_identifier\nAmara Joseph,STU-001\n"
    upload(auth_client, classroom, content)

    enrollment = Enrollment.objects.get(classroom=classroom)
    enrollment.is_active = False
    enrollment.save(update_fields=["is_active"])

    response = upload(auth_client, classroom, content)
    assert response.data["reactivated_enrollments"] == 1
    enrollment.refresh_from_db()
    assert enrollment.is_active


def test_utf8_bom_and_accented_names_are_handled(auth_client, classroom):
    content = "\ufeffdisplay_name,school_identifier\nJosé Ramírez,STU-010\n"
    handle = io.BytesIO(content.encode("utf-8"))
    handle.name = "roster.csv"
    response = auth_client.post(
        reverse("classroom-import-roster", args=[classroom.pk]),
        {"file": handle},
        format="multipart",
    )
    assert response.status_code == 200
    assert Student.objects.get(school_identifier="STU-010").display_name == "José Ramírez"


def test_non_csv_upload_is_rejected(auth_client, classroom):
    response = upload(auth_client, classroom, "display_name\nX\n", filename="roster.txt")
    assert response.status_code == 400


def test_empty_file_is_rejected(auth_client, classroom):
    response = upload(auth_client, classroom, "")
    assert response.status_code == 400


def test_a_teacher_cannot_import_into_another_teachers_class(other_client, classroom):
    response = upload(other_client, classroom, "display_name\nAmara Joseph\n")
    assert response.status_code == 404
    assert Student.objects.count() == 0


def test_the_downloadable_template_imports_cleanly(auth_client, classroom):
    """The template we hand teachers must satisfy our own validator."""
    template = auth_client.get(reverse("roster-csv-template"))
    assert template.status_code == 200
    assert template["Content-Type"].startswith("text/csv")
    body = template.content.decode("utf-8")
    assert body == SAMPLE_CSV

    response = upload(auth_client, classroom, body)
    assert response.status_code == 200
    assert response.data["created_students"] == 4
    assert response.data["row_errors"] == []
