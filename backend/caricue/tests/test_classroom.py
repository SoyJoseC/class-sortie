"""Class creation, editing and manual roster management."""

from __future__ import annotations

import pytest
from django.urls import reverse

from caricue.classroom.models import Classroom, Enrollment, Student

pytestmark = pytest.mark.django_db


def test_create_class(auth_client, teacher):
    response = auth_client.post(
        reverse("classroom-list"),
        {
            "name": "Form 4 Information Technology",
            "subject": "Information Technology",
            "level": "Form 4",
            "academic_period": "2026 Term 1",
        },
        format="json",
    )
    assert response.status_code == 201
    assert response.data["roster_size"] == 0

    classroom = Classroom.objects.get(pk=response.data["id"])
    # The owner comes from the session, never from the request body.
    assert classroom.teacher == teacher


def test_teacher_field_in_the_payload_is_ignored(auth_client, teacher, other_teacher):
    response = auth_client.post(
        reverse("classroom-list"),
        {"name": "Assigned elsewhere", "teacher": other_teacher.pk},
        format="json",
    )
    assert response.status_code == 201
    assert Classroom.objects.get(pk=response.data["id"]).teacher == teacher


def test_class_name_is_required(auth_client):
    response = auth_client.post(reverse("classroom-list"), {"name": "   "}, format="json")
    assert response.status_code == 400
    assert "name" in response.data["errors"]


def test_duplicate_class_name_for_same_teacher_is_rejected(auth_client, classroom):
    response = auth_client.post(
        reverse("classroom-list"),
        {"name": classroom.name.upper()},
        format="json",
    )
    assert response.status_code == 400
    assert "name" in response.data["errors"]


def test_two_teachers_may_use_the_same_class_name(auth_client, other_client, classroom):
    response = other_client.post(
        reverse("classroom-list"), {"name": classroom.name}, format="json"
    )
    assert response.status_code == 201


def test_edit_class(auth_client, classroom):
    response = auth_client.patch(
        reverse("classroom-detail", args=[classroom.pk]),
        {"subject": "Digital Literacy", "academic_period": "2026 Term 2"},
        format="json",
    )
    assert response.status_code == 200
    classroom.refresh_from_db()
    assert classroom.subject == "Digital Literacy"


def test_add_student_manually_creates_and_enrols(auth_client, classroom, teacher):
    response = auth_client.post(
        reverse("classroom-add-student", args=[classroom.pk]),
        {"display_name": "Amara Joseph", "school_identifier": "STU-001"},
        format="json",
    )
    assert response.status_code == 201
    student = Student.objects.get(pk=response.data["id"])
    assert student.teacher == teacher
    assert Enrollment.objects.filter(classroom=classroom, student=student).exists()


def test_add_student_requires_a_display_name(auth_client, classroom):
    response = auth_client.post(
        reverse("classroom-add-student", args=[classroom.pk]),
        {"display_name": "  "},
        format="json",
    )
    assert response.status_code == 400


def test_duplicate_school_identifier_is_rejected(
    auth_client, classroom, make_student, teacher
):
    make_student(teacher, "Existing", "STU-001")
    response = auth_client.post(
        reverse("classroom-add-student", args=[classroom.pk]),
        {"display_name": "Different Person", "school_identifier": "stu-001"},
        format="json",
    )
    assert response.status_code == 400
    assert "school_identifier" in response.data["errors"]


def test_students_may_share_a_display_name(auth_client, classroom):
    url = reverse("classroom-add-student", args=[classroom.pk])
    assert (
        auth_client.post(url, {"display_name": "Devon C"}, format="json").status_code
        == 201
    )
    assert (
        auth_client.post(url, {"display_name": "Devon C"}, format="json").status_code
        == 201
    )


def test_roster_lists_enrolled_students(auth_client, classroom, enrolled_students):
    response = auth_client.get(reverse("classroom-roster", args=[classroom.pk]))
    assert response.status_code == 200
    assert len(response.data) == len(enrolled_students)
    assert response.data[0]["student_detail"]["display_name"] == "Student 1"


def test_roster_size_counts_only_active_enrolments(
    auth_client, classroom, enrolled_students
):
    enrollment = Enrollment.objects.filter(classroom=classroom).first()
    enrollment.is_active = False
    enrollment.save(update_fields=["is_active"])

    response = auth_client.get(reverse("classroom-detail", args=[classroom.pk]))
    assert response.data["roster_size"] == len(enrolled_students) - 1


def test_a_student_cannot_be_enrolled_twice_in_one_class(
    auth_client, classroom, make_student, teacher
):
    student = make_student(teacher, "Amara Joseph", "STU-001")
    url = reverse("enrollment-list")
    payload = {"classroom": classroom.pk, "student": student.pk}

    assert auth_client.post(url, payload, format="json").status_code == 201
    duplicate = auth_client.post(url, payload, format="json")
    assert duplicate.status_code == 400
    assert Enrollment.objects.filter(classroom=classroom, student=student).count() == 1


def test_one_student_may_be_enrolled_in_several_classes(
    auth_client, make_classroom, make_student, teacher
):
    student = make_student(teacher, "Amara Joseph", "STU-001")
    first = make_classroom(teacher, "Form 4 IT")
    second = make_classroom(teacher, "Form 5 IT")

    for classroom in (first, second):
        response = auth_client.post(
            reverse("enrollment-list"),
            {"classroom": classroom.pk, "student": student.pk},
            format="json",
        )
        assert response.status_code == 201
    assert Enrollment.objects.filter(student=student).count() == 2


def test_students_can_be_filtered_by_class(
    auth_client, classroom, make_classroom, make_student, teacher, enrolled_students
):
    other_class = make_classroom(teacher, "Form 5 IT")
    outsider = make_student(teacher, "Not In Class", "STU-999")
    Enrollment.objects.create(classroom=other_class, student=outsider)

    response = auth_client.get(reverse("student-list"), {"classroom": classroom.pk})
    names = {row["display_name"] for row in response.data["results"]}
    assert "Not In Class" not in names
    assert len(names) == len(enrolled_students)


def test_deleting_a_class_removes_its_enrolments_but_keeps_students(
    auth_client, classroom, enrolled_students
):
    response = auth_client.delete(reverse("classroom-detail", args=[classroom.pk]))
    assert response.status_code == 204
    assert not Enrollment.objects.filter(classroom_id=classroom.pk).exists()
    # Students belong to the teacher, not the class, so they survive.
    assert Student.objects.filter(pk__in=[s.pk for s in enrolled_students]).count() == 4
