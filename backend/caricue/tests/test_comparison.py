"""Session comparison and topic timeline."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from caricue.activities.follow_up import create_follow_up_activity
from caricue.activities.models import ActivityStatus, QuestionType
from caricue.insights.comparison import (
    build_session_comparison,
    build_topic_timeline,
    find_baseline_session,
)
from caricue.live.models import PlanImpact, TeacherReflection
from caricue.live.services import (
    close_session,
    join_session,
    launch_session,
    submit_responses,
)

pytestmark = pytest.mark.django_db


def submit(session, activity, identifier: str, answers: list[dict]):
    result = join_session(session=session, identifier=identifier)
    return submit_responses(
        session=session, participant=result.participant, answers=answers
    )


def answer_set(activity, *, mcq_correct: bool, confidence: int):
    payload = []
    for question in activity.questions.prefetch_related("choices").order_by("position"):
        if question.question_type == QuestionType.MULTIPLE_CHOICE:
            choice = question.choices.filter(is_correct=mcq_correct).first()
            entry = {"question": question.pk, "selected_choice": choice.pk}
            if question.collect_confidence:
                entry["confidence_value"] = confidence
            payload.append(entry)
        elif question.question_type == QuestionType.SHORT_TEXT:
            if question.normalized_accepted_answers():
                text = "Random Access Memory" if mcq_correct else "Read Access Memory"
            else:
                text = "A switch is local."
            payload.append({"question": question.pk, "text_response": text})
        elif question.question_type == QuestionType.CONFIDENCE:
            payload.append({"question": question.pk, "confidence_value": confidence})
    return payload


def test_explicit_follow_up_baseline_used(teacher, classroom, make_activity):
    baseline_activity = make_activity(teacher, classroom, title="Baseline check")
    baseline_session, _ = launch_session(activity=baseline_activity)
    submit(
        baseline_session,
        baseline_activity,
        "S1",
        answer_set(baseline_activity, mcq_correct=False, confidence=4),
    )
    close_session(baseline_session)
    baseline_session.closed_at = timezone.now() - timedelta(days=3)
    baseline_session.save(update_fields=["closed_at"])

    follow_up_activity = create_follow_up_activity(
        baseline_session, teacher, include_confidence=False
    )
    follow_up_activity.status = ActivityStatus.PUBLISHED
    follow_up_activity.save(update_fields=["status"])

    current_session, _ = launch_session(activity=follow_up_activity)
    submit(
        current_session,
        follow_up_activity,
        "S1",
        answer_set(follow_up_activity, mcq_correct=True, confidence=4),
    )
    close_session(current_session)

    baseline = find_baseline_session(current_session)
    assert baseline.pk == baseline_session.pk


def test_overall_delta_math(teacher, classroom, make_activity):
    activity = make_activity(teacher, classroom)
    baseline_session, _ = launch_session(activity=activity)
    submit(
        baseline_session,
        activity,
        "S1",
        answer_set(activity, mcq_correct=False, confidence=4),
    )
    close_session(baseline_session)
    baseline_session.closed_at = timezone.now() - timedelta(days=2)
    baseline_session.save(update_fields=["closed_at"])

    follow_up = create_follow_up_activity(
        baseline_session, teacher, include_confidence=False
    )
    follow_up.status = ActivityStatus.PUBLISHED
    follow_up.save(update_fields=["status"])

    current_session, _ = launch_session(activity=follow_up)
    submit(
        current_session,
        follow_up,
        "S1",
        answer_set(follow_up, mcq_correct=True, confidence=4),
    )
    close_session(current_session)

    comparison = build_session_comparison(current_session)
    assert comparison is not None
    assert comparison.overall_delta is not None
    assert comparison.overall_delta > 0


def test_roster_student_movement(roster_session, activity, enrolled_students):
    baseline = roster_session
    submit(
        baseline,
        activity,
        enrolled_students[0].school_identifier,
        answer_set(activity, mcq_correct=False, confidence=5),
    )
    close_session(baseline)
    baseline.closed_at = timezone.now() - timedelta(days=1)
    baseline.save(update_fields=["closed_at"])

    follow_up = create_follow_up_activity(
        baseline, activity.teacher, include_confidence=False
    )
    follow_up.status = ActivityStatus.PUBLISHED
    follow_up.save(update_fields=["status"])

    current, _ = launch_session(activity=follow_up, identity_mode="roster_identifier")
    submit(
        current,
        follow_up,
        enrolled_students[0].school_identifier,
        answer_set(follow_up, mcq_correct=True, confidence=4),
    )
    close_session(current)

    comparison = build_session_comparison(current)
    assert comparison.tracking_mode == "roster"
    assert comparison.student_movement is not None
    assert comparison.student_movement.improved_count >= 1


def test_display_name_mode_class_only(open_session, activity):
    baseline = open_session
    submit(
        baseline,
        activity,
        "Alice",
        answer_set(activity, mcq_correct=False, confidence=4),
    )
    close_session(baseline)
    baseline.closed_at = timezone.now() - timedelta(days=1)
    baseline.save(update_fields=["closed_at"])

    follow_up = create_follow_up_activity(
        baseline, activity.teacher, include_confidence=False
    )
    follow_up.status = ActivityStatus.PUBLISHED
    follow_up.save(update_fields=["status"])

    current, _ = launch_session(activity=follow_up)
    submit(
        current,
        follow_up,
        "Alice",
        answer_set(follow_up, mcq_correct=True, confidence=4),
    )
    close_session(current)

    comparison = build_session_comparison(current)
    assert comparison.tracking_mode == "class_only"
    assert comparison.student_movement is None


def test_topic_timeline_groups_sessions(classroom, teacher, make_activity):
    activity = make_activity(teacher, classroom, topic="Networking")
    session_a, _ = launch_session(activity=activity)
    close_session(session_a)
    session_b, _ = launch_session(activity=activity)
    close_session(session_b)

    timeline = build_topic_timeline(classroom)
    assert len(timeline) >= 1
    networking = next(
        (g for g in timeline if "networking" in g["topic"].lower() or g["topic"]),
        timeline[0],
    )
    assert len(networking["sessions"]) >= 2


def test_results_includes_comparison(auth_client, teacher, classroom, make_activity):
    activity = make_activity(teacher, classroom)
    baseline, _ = launch_session(activity=activity)
    submit(
        baseline,
        activity,
        "S1",
        answer_set(activity, mcq_correct=False, confidence=4),
    )
    close_session(baseline)
    baseline.closed_at = timezone.now() - timedelta(days=2)
    baseline.save(update_fields=["closed_at"])
    TeacherReflection.objects.create(
        live_session=baseline,
        primary_gap="Storage confusion",
        plan_impact=PlanImpact.CHANGED,
        planned_action="Reteach SSD vs RAM",
    )

    follow_up = create_follow_up_activity(baseline, teacher, include_confidence=False)
    follow_up.status = ActivityStatus.PUBLISHED
    follow_up.save(update_fields=["status"])

    current, _ = launch_session(activity=follow_up)
    submit(
        current,
        follow_up,
        "S1",
        answer_set(follow_up, mcq_correct=True, confidence=4),
    )
    close_session(current)

    url = reverse("livesession-results", args=[current.pk])
    response = auth_client.get(url)
    assert response.status_code == 200
    assert response.data["comparison"] is not None
    assert response.data["comparison"]["kind"] == "fact"


def test_topic_timeline_owner_isolation(other_client, classroom):
    url = reverse("classroom-topic-timeline", args=[classroom.pk])
    response = other_client.get(url)
    assert response.status_code == 404
