"""Session launch, close, code/token generation and reflections."""

from __future__ import annotations

import pytest
from django.urls import reverse

from caricue.activities.models import ActivityStatus
from caricue.live.models import (
    CODE_ALPHABET,
    IdentityMode,
    LiveSession,
    PlanImpact,
    SessionStatus,
    TeacherReflection,
)

pytestmark = pytest.mark.django_db


def test_launch_creates_an_open_session(auth_client, activity):
    response = auth_client.post(reverse("activity-launch", args=[activity.pk]))

    assert response.status_code == 201
    assert response.data["status"] == SessionStatus.OPEN
    assert response.data["closed_at"] is None
    # The dashboard poll interval is advertised by the API, not hard-coded
    # in the frontend.
    assert 3 <= response.data["poll_interval_seconds"] <= 5


def test_launching_publishes_a_draft_activity(auth_client, activity):
    assert activity.status == ActivityStatus.DRAFT
    auth_client.post(reverse("activity-launch", args=[activity.pk]))
    activity.refresh_from_db()
    assert activity.status == ActivityStatus.PUBLISHED


def test_short_code_is_unambiguous_and_unique(auth_client, activity):
    codes = set()
    for _ in range(5):
        response = auth_client.post(reverse("activity-launch", args=[activity.pk]))
        code = response.data["code"]
        assert len(code) == 6
        # No 0/O/1/I/L: the teacher reads this aloud.
        assert set(code) <= set(CODE_ALPHABET)
        codes.add(code)
    assert len(codes) == 5


def test_public_token_is_long_and_distinct_from_the_code(auth_client, activity):
    response = auth_client.post(reverse("activity-launch", args=[activity.pk]))
    token = response.data["public_token"]
    assert len(token) == 32
    assert token != response.data["code"]


def test_join_url_uses_the_configured_public_base_url(auth_client, activity, settings):
    settings.PUBLIC_BASE_URL = "https://caricue.example.org"
    response = auth_client.post(reverse("activity-launch", args=[activity.pk]))
    assert response.data["join_url"] == (
        f"https://caricue.example.org/s/{response.data['public_token']}"
    )


def test_activity_without_questions_cannot_be_launched(
    auth_client, make_activity, teacher, classroom
):
    activity = make_activity(teacher, classroom, with_questions=False)
    response = auth_client.post(reverse("activity-launch", args=[activity.pk]))
    assert response.status_code == 400
    assert not LiveSession.objects.filter(activity=activity).exists()


def test_launch_in_roster_mode_requires_roster_identifiers(
    auth_client, activity, make_student, teacher, classroom
):
    from caricue.classroom.models import Enrollment

    student = make_student(teacher, "No Identifier", "")
    Enrollment.objects.create(classroom=classroom, student=student)

    response = auth_client.post(
        reverse("activity-launch", args=[activity.pk]),
        {"identity_mode": IdentityMode.ROSTER_IDENTIFIER},
        format="json",
    )
    assert response.status_code == 400
    assert "identifier" in response.data["detail"].lower()


def test_launch_in_roster_mode_succeeds_with_identifiers(
    auth_client, activity, enrolled_students
):
    response = auth_client.post(
        reverse("activity-launch", args=[activity.pk]),
        {"identity_mode": IdentityMode.ROSTER_IDENTIFIER},
        format="json",
    )
    assert response.status_code == 201
    assert response.data["identity_mode"] == IdentityMode.ROSTER_IDENTIFIER
    assert response.data["roster_size"] == 4


def test_close_session_records_the_timestamp(auth_client, open_session):
    response = auth_client.post(reverse("livesession-close", args=[open_session.pk]))
    assert response.status_code == 200
    assert response.data["status"] == SessionStatus.CLOSED
    assert response.data["closed_at"] is not None


def test_closing_twice_is_a_conflict_not_a_silent_success(auth_client, open_session):
    auth_client.post(reverse("livesession-close", args=[open_session.pk]))
    response = auth_client.post(reverse("livesession-close", args=[open_session.pk]))
    assert response.status_code == 409


def test_sessions_can_be_filtered_by_status(auth_client, activity):
    first = auth_client.post(reverse("activity-launch", args=[activity.pk])).data
    auth_client.post(reverse("activity-launch", args=[activity.pk]))
    auth_client.post(reverse("livesession-close", args=[first["id"]]))

    open_only = auth_client.get(reverse("livesession-list"), {"status": "open"})
    closed_only = auth_client.get(reverse("livesession-list"), {"status": "closed"})

    assert len(open_only.data["results"]) == 1
    assert len(closed_only.data["results"]) == 1


def test_session_list_is_not_writable(auth_client, open_session):
    """Sessions are created by launching an activity, never posted directly."""
    response = auth_client.post(reverse("livesession-list"), {}, format="json")
    assert response.status_code == 405


# --------------------------------------------------------------------------- #
# Reflections
# --------------------------------------------------------------------------- #
def test_create_reflection_after_closing(auth_client, open_session):
    auth_client.post(reverse("livesession-close", args=[open_session.pk]))

    response = auth_client.post(
        reverse("reflection-list"),
        {
            "live_session": open_session.pk,
            "primary_gap": "Students confuse switches with routers.",
            "plan_impact": PlanImpact.CHANGED,
            "planned_action": "Reteach with a packet-journey diagram tomorrow.",
            "notes": "Three students were confidently wrong.",
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.data["session_code"] == open_session.code
    assert TeacherReflection.objects.filter(live_session=open_session).exists()


def test_reflection_requires_a_gap_and_an_action(auth_client, open_session):
    response = auth_client.post(
        reverse("reflection-list"),
        {
            "live_session": open_session.pk,
            "primary_gap": "   ",
            "plan_impact": PlanImpact.CONFIRMED,
            "planned_action": "  ",
        },
        format="json",
    )
    assert response.status_code == 400
    assert "primary_gap" in response.data["errors"]
    assert "planned_action" in response.data["errors"]


def test_only_one_reflection_per_session(auth_client, open_session):
    payload = {
        "live_session": open_session.pk,
        "primary_gap": "Gap",
        "plan_impact": PlanImpact.CONFIRMED,
        "planned_action": "Action",
    }
    assert (
        auth_client.post(reverse("reflection-list"), payload, format="json").status_code
        == 201
    )
    duplicate = auth_client.post(reverse("reflection-list"), payload, format="json")
    assert duplicate.status_code == 400
    assert TeacherReflection.objects.filter(live_session=open_session).count() == 1


def test_reflection_can_be_edited(auth_client, open_session):
    created = auth_client.post(
        reverse("reflection-list"),
        {
            "live_session": open_session.pk,
            "primary_gap": "First take",
            "plan_impact": PlanImpact.UNCLEAR,
            "planned_action": "Think about it",
        },
        format="json",
    ).data

    response = auth_client.patch(
        reverse("reflection-detail", args=[created["id"]]),
        {"plan_impact": PlanImpact.CHANGED, "primary_gap": "Clearer take"},
        format="json",
    )
    assert response.status_code == 200
    assert response.data["plan_impact"] == PlanImpact.CHANGED


def test_results_endpoint_includes_the_reflection(auth_client, open_session):
    auth_client.post(
        reverse("reflection-list"),
        {
            "live_session": open_session.pk,
            "primary_gap": "Gap",
            "plan_impact": PlanImpact.CONFIRMED,
            "planned_action": "Action",
        },
        format="json",
    )
    response = auth_client.get(reverse("livesession-results", args=[open_session.pk]))
    assert response.data["reflection"]["primary_gap"] == "Gap"
    assert response.data["session"]["has_reflection"] is True
