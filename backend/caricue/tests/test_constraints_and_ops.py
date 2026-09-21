"""Database constraints, throttling, health check and the demo seed command."""

from __future__ import annotations

import pytest
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone

from caricue.accounts.models import Teacher
from caricue.activities.models import Activity, Question, QuestionType
from caricue.classroom.models import Classroom, Enrollment, Student
from caricue.live.models import (
    LiveSession,
    Participant,
    Response,
    SessionStatus,
    TeacherReflection,
)
from caricue.live.services import join_session, submit_responses

pytestmark = pytest.mark.django_db


# --------------------------------------------------------------------------- #
# Constraints
# --------------------------------------------------------------------------- #
def test_duplicate_response_is_blocked_by_the_database(open_session, activity):
    result = join_session(session=open_session, identifier="Amara J")
    question = activity.questions.get(position=2)
    Response.objects.create(
        participant=result.participant, question=question, text_response="RAM"
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        Response.objects.create(
            participant=result.participant, question=question, text_response="again"
        )


def test_duplicate_roster_participant_is_blocked(roster_session, enrolled_students):
    student = enrolled_students[0]
    Participant.objects.create(live_session=roster_session, student=student)

    with pytest.raises(IntegrityError), transaction.atomic():
        Participant.objects.create(live_session=roster_session, student=student)


def test_duplicate_display_name_participant_is_blocked(open_session):
    Participant.objects.create(live_session=open_session, display_name="Amara J")

    with pytest.raises(IntegrityError), transaction.atomic():
        Participant.objects.create(live_session=open_session, display_name="amara j")


def test_the_same_name_may_be_used_in_a_different_session(
    auth_client, activity, open_session
):
    other = auth_client.post(reverse("activity-launch", args=[activity.pk])).data
    Participant.objects.create(live_session=open_session, display_name="Amara J")
    Participant.objects.create(
        live_session=LiveSession.objects.get(pk=other["id"]), display_name="Amara J"
    )
    assert Participant.objects.filter(display_name="Amara J").count() == 2


def test_duplicate_enrollment_is_blocked(classroom, make_student, teacher):
    student = make_student(teacher, "Amara Joseph", "STU-001")
    Enrollment.objects.create(classroom=classroom, student=student)

    with pytest.raises(IntegrityError), transaction.atomic():
        Enrollment.objects.create(classroom=classroom, student=student)


def test_duplicate_class_name_per_teacher_is_blocked(teacher):
    Classroom.objects.create(teacher=teacher, name="Form 4 IT")

    with pytest.raises(IntegrityError), transaction.atomic():
        Classroom.objects.create(teacher=teacher, name="form 4 it")


def test_duplicate_school_identifier_per_teacher_is_blocked(teacher):
    Student.objects.create(teacher=teacher, display_name="A", school_identifier="STU-001")

    with pytest.raises(IntegrityError), transaction.atomic():
        Student.objects.create(
            teacher=teacher, display_name="B", school_identifier="stu-001"
        )


def test_blank_school_identifiers_do_not_collide(teacher):
    """The uniqueness constraint is conditional, so optional stays optional."""
    Student.objects.create(teacher=teacher, display_name="A", school_identifier="")
    Student.objects.create(teacher=teacher, display_name="B", school_identifier="")
    assert Student.objects.filter(school_identifier="").count() == 2


def test_duplicate_question_position_is_blocked(activity):
    with pytest.raises(IntegrityError), transaction.atomic():
        Question.objects.create(
            activity=activity,
            position=1,
            prompt="Clash",
            question_type=QuestionType.SHORT_TEXT,
        )


def test_two_reflections_on_one_session_are_blocked(open_session):
    TeacherReflection.objects.create(
        live_session=open_session, primary_gap="A", planned_action="B"
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        TeacherReflection.objects.create(
            live_session=open_session, primary_gap="C", planned_action="D"
        )


def test_a_closed_session_must_record_when_it_closed(open_session):
    with pytest.raises(IntegrityError), transaction.atomic():
        LiveSession.objects.filter(pk=open_session.pk).update(
            status=SessionStatus.CLOSED, closed_at=None
        )


def test_an_open_session_cannot_carry_a_closed_timestamp(open_session):
    with pytest.raises(IntegrityError), transaction.atomic():
        LiveSession.objects.filter(pk=open_session.pk).update(
            status=SessionStatus.OPEN, closed_at=timezone.now()
        )


def test_confidence_outside_the_scale_is_blocked(open_session, activity):
    result = join_session(session=open_session, identifier="Amara J")
    with pytest.raises(IntegrityError), transaction.atomic():
        Response.objects.create(
            participant=result.participant,
            question=activity.questions.get(position=4),
            confidence_value=7,
        )


def test_session_codes_and_tokens_are_globally_unique(open_session):
    with pytest.raises(IntegrityError), transaction.atomic():
        LiveSession.objects.create(
            activity=open_session.activity,
            classroom=open_session.classroom,
            code=open_session.code,
            public_token="a" * 32,
        )


def test_deleting_a_session_removes_its_participants_and_responses(
    open_session, activity, answers_for
):
    result = join_session(session=open_session, identifier="Amara J")
    submit_responses(
        session=open_session,
        participant=result.participant,
        answers=answers_for(activity),
    )
    assert Response.objects.count() == 4

    open_session.delete()
    assert Participant.objects.count() == 0
    assert Response.objects.count() == 0


def test_deleting_a_student_keeps_their_anonymous_responses(
    roster_session, enrolled_students, activity, answers_for
):
    """Roster removal must not silently destroy assessment evidence."""
    student = enrolled_students[0]
    result = join_session(session=roster_session, identifier=student.school_identifier)
    submit_responses(
        session=roster_session,
        participant=result.participant,
        answers=answers_for(activity),
    )

    student.delete()
    participant = Participant.objects.get(live_session=roster_session)
    assert participant.student_id is None
    assert Response.objects.filter(participant=participant).count() == 4


# --------------------------------------------------------------------------- #
# Throttling
# --------------------------------------------------------------------------- #
def test_public_code_lookup_is_throttled(api, open_session, settings):
    settings.REST_FRAMEWORK = {
        **settings.REST_FRAMEWORK,
        "DEFAULT_THROTTLE_RATES": {
            **settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"],
            "public_lookup": "3/min",
        },
    }
    from caricue.core.throttling import PublicLookupThrottle

    PublicLookupThrottle.rate = None  # force a re-read of the configured rate
    PublicLookupThrottle.THROTTLE_RATES = settings.REST_FRAMEWORK[
        "DEFAULT_THROTTLE_RATES"
    ]

    url = reverse("public-code-lookup")
    statuses = [api.get(url, {"code": open_session.code}).status_code for _ in range(5)]
    assert 429 in statuses, statuses


def test_public_join_is_throttled(api, open_session, settings):
    from caricue.core.throttling import PublicJoinThrottle

    PublicJoinThrottle.rate = None
    PublicJoinThrottle.THROTTLE_RATES = {
        **settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"],
        "public_join": "2/min",
    }

    url = reverse("public-join", args=[open_session.public_token])
    statuses = [
        api.post(url, {"identifier": f"Student {n}"}, format="json").status_code
        for n in range(4)
    ]
    assert 429 in statuses, statuses


def test_login_attempts_are_throttled(api, teacher, settings):
    from caricue.core.throttling import AuthAttemptThrottle

    AuthAttemptThrottle.rate = None
    AuthAttemptThrottle.THROTTLE_RATES = {
        **settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"],
        "auth_attempt": "3/min",
    }

    url = reverse("auth-login")
    statuses = [
        api.post(
            url, {"email": teacher.email, "password": "WrongPassword1"}, format="json"
        ).status_code
        for _ in range(5)
    ]
    assert 429 in statuses, statuses


# --------------------------------------------------------------------------- #
# Health and config
# --------------------------------------------------------------------------- #
def test_health_check_reports_the_database(api):
    response = api.get(reverse("health"))
    assert response.status_code == 200
    assert response.data["status"] == "ok"
    assert response.data["database"] == "ok"


def test_health_check_needs_no_authentication(client):
    assert client.get(reverse("health")).status_code == 200


def test_client_config_exposes_no_secrets(api, settings):
    settings.INSIGHT_LLM_API_KEY = "super-secret-value"
    response = api.get(reverse("client-config"))

    assert response.status_code == 200
    assert response.data["ai_suggestions_enabled"] is True
    assert "super-secret-value" not in str(response.data)
    assert 3 <= response.data["dashboard_poll_seconds"] <= 5
    assert response.data["max_questions"] == 5


# --------------------------------------------------------------------------- #
# Demo data
# --------------------------------------------------------------------------- #
def test_seed_demo_builds_a_complete_demonstration(settings):
    settings.DEBUG = True
    call_command("seed_demo", verbosity=0)

    teacher = Teacher.objects.get(email="teacher@caricue.demo")
    classroom = Classroom.objects.get(teacher=teacher)
    activity = Activity.objects.get(
        teacher=teacher, title="Hardware and networking check"
    )
    follow_up_activity = Activity.objects.get(
        teacher=teacher, follow_up_of_session__isnull=False
    )

    assert classroom.roster_size == 10
    assert activity.questions.count() == 5

    closed = LiveSession.objects.get(activity=activity, status=SessionStatus.CLOSED)
    follow_up_closed = LiveSession.objects.get(
        activity=follow_up_activity, status=SessionStatus.CLOSED
    )
    open_session = LiveSession.objects.get(activity=activity, status=SessionStatus.OPEN)

    assert closed.participants.filter(submitted_at__isnull=False).count() == 8
    assert Response.objects.filter(participant__live_session=closed).exists()
    assert TeacherReflection.objects.filter(live_session=closed).exists()
    assert follow_up_closed.participants.filter(submitted_at__isnull=False).count() == 8
    # The open session is the QR demo, so it must have no responses yet.
    assert open_session.participants.count() == 0
    assert open_session.join_url.endswith(open_session.public_token)


def test_seed_demo_login_works_with_the_documented_password(settings, api):
    settings.DEBUG = True
    call_command("seed_demo", verbosity=0)

    response = api.post(
        reverse("auth-login"),
        {"email": "teacher@caricue.demo", "password": "CariCueDemo2026"},
        format="json",
    )
    assert response.status_code == 200


def test_seed_demo_is_reproducible_and_rerunnable(settings):
    settings.DEBUG = True
    call_command("seed_demo", verbosity=0)
    first = Response.objects.filter(is_correct=True).count()

    call_command("seed_demo", "--reset", verbosity=0)
    second = Response.objects.filter(is_correct=True).count()

    assert first == second
    assert Teacher.objects.filter(email="teacher@caricue.demo").count() == 1


def test_seed_demo_produces_insight_worthy_data(settings):
    settings.DEBUG = True
    call_command("seed_demo", verbosity=0)

    from caricue.insights.service import build_session_insights

    closed = LiveSession.objects.get(
        status=SessionStatus.CLOSED, reflection__isnull=False
    )
    insights = build_session_insights(closed)

    # A demo is only useful if the dashboard has something to show.
    assert insights.submitted_count == 8
    assert insights.completion_percentage == 80.0
    assert insights.overall_correctness_percentage is not None
    assert insights.has_confidence_data
    assert insights.needs_attention
    assert any(q.common_answers for q in insights.questions)


def test_seed_demo_refuses_to_run_outside_debug(settings):
    from django.core.management.base import CommandError

    settings.DEBUG = False
    with pytest.raises(CommandError):
        call_command("seed_demo", verbosity=0)
    assert not Teacher.objects.filter(email="teacher@caricue.demo").exists()
