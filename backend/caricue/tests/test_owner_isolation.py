"""Owner isolation.

The single most important security property in CariCue: a teacher must never
reach another teacher's classes, students, activities, sessions or results.
These tests probe every teacher-facing collection from a second account.
"""

from __future__ import annotations

import pytest
from django.urls import reverse

from caricue.classroom.models import Enrollment
from caricue.live.models import PlanImpact, TeacherReflection

pytestmark = pytest.mark.django_db


def test_classroom_list_only_contains_own_classes(
    auth_client, other_client, make_classroom, teacher, other_teacher
):
    make_classroom(teacher, "Mine")
    make_classroom(other_teacher, "Theirs")

    mine = auth_client.get(reverse("classroom-list"))
    theirs = other_client.get(reverse("classroom-list"))

    assert [row["name"] for row in mine.data["results"]] == ["Mine"]
    assert [row["name"] for row in theirs.data["results"]] == ["Theirs"]


@pytest.mark.parametrize("method", ["get", "put", "patch", "delete"])
def test_foreign_classroom_is_not_reachable(other_client, classroom, method):
    url = reverse("classroom-detail", args=[classroom.pk])
    response = getattr(other_client, method)(url, {}, format="json")
    # 404, not 403: the response must not confirm that the id exists.
    assert response.status_code == 404


def test_foreign_student_is_not_reachable(other_client, make_student, teacher):
    student = make_student(teacher, "Amara Joseph", "STU-001")
    response = other_client.get(reverse("student-detail", args=[student.pk]))
    assert response.status_code == 404


def test_foreign_activity_is_not_reachable(other_client, activity):
    assert (
        other_client.get(reverse("activity-detail", args=[activity.pk])).status_code
        == 404
    )


def test_foreign_activity_cannot_be_launched(other_client, activity):
    response = other_client.post(reverse("activity-launch", args=[activity.pk]))
    assert response.status_code == 404


def test_foreign_session_results_are_not_reachable(other_client, open_session):
    for name in ("livesession-detail", "livesession-dashboard", "livesession-results"):
        response = other_client.get(reverse(name, args=[open_session.pk]))
        assert response.status_code == 404, name


def test_foreign_session_cannot_be_closed(other_client, open_session):
    response = other_client.post(reverse("livesession-close", args=[open_session.pk]))
    assert response.status_code == 404
    open_session.refresh_from_db()
    assert open_session.is_open


def test_foreign_roster_cannot_be_read(other_client, classroom, enrolled_students):
    response = other_client.get(reverse("classroom-roster", args=[classroom.pk]))
    assert response.status_code == 404


def test_cannot_enrol_a_foreign_student_in_own_class(
    other_client, make_classroom, make_student, teacher, other_teacher
):
    foreign_student = make_student(teacher, "Amara Joseph", "STU-001")
    own_class = make_classroom(other_teacher, "Intruder class")

    response = other_client.post(
        reverse("enrollment-list"),
        {"classroom": own_class.pk, "student": foreign_student.pk},
        format="json",
    )
    assert response.status_code == 400
    assert not Enrollment.objects.filter(student=foreign_student).exists()


def test_cannot_attach_own_student_to_a_foreign_class(
    other_client, classroom, make_student, other_teacher
):
    own_student = make_student(other_teacher, "Their Student", "OTH-001")
    response = other_client.post(
        reverse("enrollment-list"),
        {"classroom": classroom.pk, "student": own_student.pk},
        format="json",
    )
    assert response.status_code == 400


def test_cannot_create_an_activity_in_a_foreign_class(other_client, classroom):
    response = other_client.post(
        reverse("activity-list"),
        {"classroom": classroom.pk, "title": "Sneaky", "questions": []},
        format="json",
    )
    assert response.status_code == 400
    assert "classroom" in response.data["errors"]


def test_cannot_write_a_reflection_on_a_foreign_session(other_client, open_session):
    response = other_client.post(
        reverse("reflection-list"),
        {
            "live_session": open_session.pk,
            "primary_gap": "Nothing",
            "plan_impact": PlanImpact.CONFIRMED,
            "planned_action": "Nothing",
        },
        format="json",
    )
    assert response.status_code == 400
    assert not TeacherReflection.objects.filter(live_session=open_session).exists()


def test_foreign_question_and_choice_are_not_reachable(other_client, activity):
    question = activity.questions.first()
    choice = question.choices.first()
    assert (
        other_client.get(reverse("question-detail", args=[question.pk])).status_code
        == 404
    )
    assert other_client.get(reverse("choice-detail", args=[choice.pk])).status_code == 404


def test_overview_is_scoped_to_the_requesting_teacher(
    other_client, classroom, activity, open_session
):
    response = other_client.get(reverse("teacher-overview"))
    assert response.status_code == 200
    assert response.data["classrooms"] == []
    assert response.data["recent_activities"] == []
    assert response.data["open_sessions"] == []
    assert response.data["counts"]["students"] == 0


def test_all_teacher_collections_require_authentication(api):
    for name in (
        "classroom-list",
        "student-list",
        "enrollment-list",
        "activity-list",
        "question-list",
        "choice-list",
        "livesession-list",
        "reflection-list",
        "teacher-overview",
        "roster-csv-template",
    ):
        assert api.get(reverse(name)).status_code == 403, name
