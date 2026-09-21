"""Follow-up draft activity generation."""

from __future__ import annotations

import pytest
from django.urls import reverse

from caricue.activities.follow_up import create_follow_up_activity
from caricue.activities.models import ActivityStatus, QuestionType
from caricue.insights.misconceptions import build_misconception_cards
from caricue.insights.service import build_session_insights
from caricue.live.services import close_session, join_session, submit_responses

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


def test_post_creates_draft_with_lineage(auth_client, teacher, open_session, activity):
    submit(
        open_session,
        activity,
        "Wrong",
        answer_set(activity, mcq_correct=False, confidence=5),
    )
    close_session(open_session)

    url = reverse("livesession-follow-up-activity", args=[open_session.pk])
    response = auth_client.post(url, {"include_confidence": True}, format="json")

    assert response.status_code == 201
    activity_id = response.data["activity_id"]

    from caricue.activities.models import Activity

    follow_up = Activity.objects.get(pk=activity_id)
    assert follow_up.status == ActivityStatus.DRAFT
    assert follow_up.classroom_id == activity.classroom_id
    assert follow_up.topic == activity.topic
    assert follow_up.follow_up_of_session_id == open_session.pk
    assert follow_up.title.startswith("Follow-up:")


def test_generated_questions_have_valid_mcq(auth_client, teacher, open_session, activity):
    submit(
        open_session,
        activity,
        "Wrong",
        answer_set(activity, mcq_correct=False, confidence=5),
    )
    close_session(open_session)

    follow_up = create_follow_up_activity(open_session, teacher)
    mcq = follow_up.questions.filter(question_type=QuestionType.MULTIPLE_CHOICE).first()
    assert mcq is not None
    assert mcq.choices.filter(is_correct=True).exists()
    assert mcq.source_question_id is not None
    assert mcq.source_session_id == open_session.pk


def test_launchability(auth_client, teacher, open_session, activity):
    submit(
        open_session,
        activity,
        "Wrong",
        answer_set(activity, mcq_correct=False, confidence=5),
    )
    close_session(open_session)

    follow_up = create_follow_up_activity(open_session, teacher)
    launchable, reason = follow_up.is_launchable()
    assert launchable, reason


def test_owner_isolation(other_client, open_session, activity):
    submit(
        open_session,
        activity,
        "Wrong",
        answer_set(activity, mcq_correct=False, confidence=5),
    )
    close_session(open_session)

    url = reverse("livesession-follow-up-activity", args=[open_session.pk])
    response = other_client.post(url, {}, format="json")
    assert response.status_code == 404


def test_filter_by_question_ids(teacher, open_session, activity):
    for index in range(3):
        submit(
            open_session,
            activity,
            f"S{index}",
            answer_set(activity, mcq_correct=False, confidence=5),
        )
    close_session(open_session)

    cards = build_misconception_cards(build_session_insights(open_session))
    assert cards
    target_id = cards[0].question_id

    follow_up = create_follow_up_activity(
        open_session, teacher, question_ids=[target_id], include_confidence=False
    )
    assert follow_up.questions.filter(source_question_id=target_id).exists()
