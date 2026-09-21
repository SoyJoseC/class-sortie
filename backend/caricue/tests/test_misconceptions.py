"""Misconception cards and API exposure."""

from __future__ import annotations

import pytest
from django.urls import reverse

from caricue.activities.models import QuestionType
from caricue.insights.misconceptions import build_misconception_cards
from caricue.insights.service import build_session_insights
from caricue.live.services import close_session, join_session, submit_responses

pytestmark = pytest.mark.django_db


def submit(session, activity, identifier: str, answers: list[dict]):
    result = join_session(session=session, identifier=identifier)
    return submit_responses(
        session=session, participant=result.participant, answers=answers
    )


def answer_set(activity, *, mcq_correct: bool, confidence: int, ram_correct: bool = True):
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
                text = "Random Access Memory" if ram_correct else "Read Access Memory"
            else:
                text = "A switch is local, a router joins networks."
            payload.append({"question": question.pk, "text_response": text})
        elif question.question_type == QuestionType.CONFIDENCE:
            payload.append({"question": question.pk, "confidence_value": confidence})
    return payload


def test_weak_mcq_produces_card_with_top_distractor(open_session, activity):
    for index in range(4):
        submit(
            open_session,
            activity,
            f"Student {index}",
            answer_set(activity, mcq_correct=False, confidence=5),
        )
    submit(
        open_session,
        activity,
        "Correct one",
        answer_set(activity, mcq_correct=True, confidence=4),
    )

    insights = build_session_insights(open_session)
    cards = build_misconception_cards(insights)

    assert len(cards) >= 1
    mcq_card = next(c for c in cards if c.question_type == QuestionType.MULTIPLE_CHOICE)
    assert mcq_card.correctness_percentage < 60
    assert any(f.label == "Top wrong choice" for f in mcq_card.facts)
    assert mcq_card.suggestion is not None
    assert mcq_card.suggestion.kind == "suggestion"


def test_high_confidence_wrong_count_attached(open_session, activity):
    submit(
        open_session,
        activity,
        "Overconfident",
        answer_set(activity, mcq_correct=False, confidence=5),
    )

    insights = build_session_insights(open_session)
    cards = build_misconception_cards(insights)

    assert cards
    assert cards[0].high_confidence_wrong_count >= 1


def test_short_text_common_wrong_answer_card(open_session, activity):
    for _ in range(3):
        submit(
            open_session,
            activity,
            f"Wrong {_}",
            answer_set(activity, mcq_correct=True, confidence=4, ram_correct=False),
        )

    insights = build_session_insights(open_session)
    cards = build_misconception_cards(insights)

    text_cards = [c for c in cards if c.question_type == QuestionType.SHORT_TEXT]
    assert text_cards
    assert any(f.label == "Common wrong answer" for f in text_cards[0].facts)


def test_no_cards_when_all_above_threshold(open_session, activity):
    submit(
        open_session,
        activity,
        "Perfect",
        answer_set(activity, mcq_correct=True, confidence=4),
    )

    cards = build_misconception_cards(build_session_insights(open_session))
    assert cards == []


def test_results_endpoint_includes_misconception_cards(
    auth_client, open_session, activity
):
    submit(
        open_session,
        activity,
        "Wrong",
        answer_set(activity, mcq_correct=False, confidence=5),
    )
    close_session(open_session)

    url = reverse("livesession-results", args=[open_session.pk])
    response = auth_client.get(url)

    assert response.status_code == 200
    assert "misconception_cards" in response.data
    assert len(response.data["misconception_cards"]) >= 1


def test_misconceptions_action_returns_cards_only(auth_client, open_session, activity):
    submit(
        open_session,
        activity,
        "Wrong",
        answer_set(activity, mcq_correct=False, confidence=5),
    )

    url = reverse("livesession-misconceptions", args=[open_session.pk])
    response = auth_client.get(url)

    assert response.status_code == 200
    assert "misconception_cards" in response.data
    assert "facts" not in response.data


def test_dashboard_includes_misconception_cards(auth_client, open_session, activity):
    submit(
        open_session,
        activity,
        "Wrong",
        answer_set(activity, mcq_correct=False, confidence=5),
    )

    url = reverse("livesession-dashboard", args=[open_session.pk])
    response = auth_client.get(url)

    assert response.status_code == 200
    assert len(response.data["misconception_cards"]) >= 1
