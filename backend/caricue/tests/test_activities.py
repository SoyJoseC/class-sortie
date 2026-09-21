"""Activity builder: creation, validation, reordering, preview."""

from __future__ import annotations

import pytest
from django.urls import reverse

from caricue.activities.models import Activity, ActivityStatus, QuestionType

pytestmark = pytest.mark.django_db


def mcq(prompt: str = "Which device routes between networks?") -> dict:
    return {
        "prompt": prompt,
        "question_type": QuestionType.MULTIPLE_CHOICE,
        "collect_confidence": True,
        "choices": [
            {"text": "Router", "is_correct": True},
            {"text": "Switch", "is_correct": False},
        ],
    }


def test_create_activity_with_nested_questions(auth_client, classroom, teacher):
    response = auth_client.post(
        reverse("activity-list"),
        {
            "classroom": classroom.pk,
            "title": "Networking check",
            "topic": "Switches and routers",
            "questions": [
                mcq(),
                {
                    "prompt": "What does RAM stand for?",
                    "question_type": QuestionType.SHORT_TEXT,
                    "accepted_answers": ["Random Access Memory", "random access memory"],
                },
                {
                    "prompt": "How confident are you?",
                    "question_type": QuestionType.CONFIDENCE,
                },
            ],
        },
        format="json",
    )

    assert response.status_code == 201
    activity = Activity.objects.get(pk=response.data["id"])
    assert activity.teacher == teacher
    assert activity.status == ActivityStatus.DRAFT
    assert [q.position for q in activity.questions.all()] == [1, 2, 3]

    # Duplicate accepted answers collapse under normalisation.
    short_text = activity.questions.get(position=2)
    assert short_text.accepted_answers == ["Random Access Memory"]
    assert short_text.is_auto_scored


def test_activity_saved_as_draft_by_default(auth_client, classroom):
    response = auth_client.post(
        reverse("activity-list"),
        {"classroom": classroom.pk, "title": "Draft", "questions": [mcq()]},
        format="json",
    )
    assert response.data["status"] == ActivityStatus.DRAFT


def test_title_is_required(auth_client, classroom):
    response = auth_client.post(
        reverse("activity-list"),
        {"classroom": classroom.pk, "title": "  ", "questions": []},
        format="json",
    )
    assert response.status_code == 400
    assert "title" in response.data["errors"]


def test_more_than_five_questions_is_rejected(auth_client, classroom):
    response = auth_client.post(
        reverse("activity-list"),
        {
            "classroom": classroom.pk,
            "title": "Too long",
            "questions": [mcq(f"Question {n}") for n in range(6)],
        },
        format="json",
    )
    assert response.status_code == 400
    assert "questions" in response.data["errors"]


def test_multiple_choice_needs_at_least_two_choices(auth_client, classroom):
    response = auth_client.post(
        reverse("activity-list"),
        {
            "classroom": classroom.pk,
            "title": "Bad MCQ",
            "questions": [
                {
                    "prompt": "Only one option",
                    "question_type": QuestionType.MULTIPLE_CHOICE,
                    "choices": [{"text": "Router", "is_correct": True}],
                }
            ],
        },
        format="json",
    )
    assert response.status_code == 400


def test_multiple_choice_needs_a_correct_answer_marked(auth_client, classroom):
    response = auth_client.post(
        reverse("activity-list"),
        {
            "classroom": classroom.pk,
            "title": "No key",
            "questions": [
                {
                    "prompt": "Which one?",
                    "question_type": QuestionType.MULTIPLE_CHOICE,
                    "choices": [
                        {"text": "Router", "is_correct": False},
                        {"text": "Switch", "is_correct": False},
                    ],
                }
            ],
        },
        format="json",
    )
    assert response.status_code == 400
    assert "correct" in str(response.data["errors"]).lower()


def test_duplicate_choice_text_is_rejected(auth_client, classroom):
    response = auth_client.post(
        reverse("activity-list"),
        {
            "classroom": classroom.pk,
            "title": "Dupes",
            "questions": [
                {
                    "prompt": "Which one?",
                    "question_type": QuestionType.MULTIPLE_CHOICE,
                    "choices": [
                        {"text": "Router", "is_correct": True},
                        {"text": "router", "is_correct": False},
                    ],
                }
            ],
        },
        format="json",
    )
    assert response.status_code == 400


def test_short_text_question_cannot_carry_choices(auth_client, classroom):
    response = auth_client.post(
        reverse("activity-list"),
        {
            "classroom": classroom.pk,
            "title": "Mixed up",
            "questions": [
                {
                    "prompt": "Explain",
                    "question_type": QuestionType.SHORT_TEXT,
                    "choices": [{"text": "Nope", "is_correct": True}],
                }
            ],
        },
        format="json",
    )
    assert response.status_code == 400


def test_short_text_without_accepted_answers_is_not_auto_scored(auth_client, classroom):
    response = auth_client.post(
        reverse("activity-list"),
        {
            "classroom": classroom.pk,
            "title": "Open ended",
            "questions": [
                {
                    "prompt": "Explain in your own words",
                    "question_type": QuestionType.SHORT_TEXT,
                    "accepted_answers": [],
                }
            ],
        },
        format="json",
    )
    assert response.status_code == 201
    assert response.data["questions"][0]["is_auto_scored"] is False


def test_updating_an_activity_reorders_questions(auth_client, activity):
    detail = reverse("activity-detail", args=[activity.pk])
    current = auth_client.get(detail).data

    reordered = list(reversed(current["questions"]))
    response = auth_client.put(
        detail,
        {
            "classroom": current["classroom"],
            "title": current["title"],
            "topic": current["topic"],
            "questions": reordered,
        },
        format="json",
    )

    assert response.status_code == 200
    prompts = [q["prompt"] for q in response.data["questions"]]
    assert prompts == [q["prompt"] for q in reordered]
    # Positions are renumbered by the server, not trusted from the client.
    assert [q["position"] for q in response.data["questions"]] == [1, 2, 3, 4]


def test_preview_never_exposes_the_answer_key(auth_client, activity):
    response = auth_client.get(reverse("activity-preview", args=[activity.pk]))
    assert response.status_code == 200

    body = str(response.data)
    assert "is_correct" not in body
    assert "accepted_answers" not in body

    mcq_question = next(
        question
        for question in response.data["questions"]
        if question["question_type"] == QuestionType.MULTIPLE_CHOICE
    )
    assert len(mcq_question["choices"]) == 3


def test_publishing_without_questions_is_rejected(auth_client, classroom):
    response = auth_client.post(
        reverse("activity-list"),
        {
            "classroom": classroom.pk,
            "title": "Empty",
            "status": ActivityStatus.PUBLISHED,
            "questions": [],
        },
        format="json",
    )
    assert response.status_code == 400


def test_list_view_reports_question_counts(auth_client, activity):
    response = auth_client.get(reverse("activity-list"))
    assert response.status_code == 200
    row = response.data["results"][0]
    assert row["question_count"] == 4
    assert row["classroom_name"] == activity.classroom.name


def test_standalone_question_create_requires_an_owned_activity(
    auth_client, other_client, activity
):
    payload = {
        "activity": activity.pk,
        "prompt": "Added later",
        "question_type": QuestionType.SHORT_TEXT,
        "accepted_answers": ["yes"],
    }
    assert (
        other_client.post(reverse("question-list"), payload, format="json").status_code
        == 400
    )

    # The fixture activity holds four questions, so the fifth is accepted and
    # the sixth hits the per-activity cap.
    fifth = auth_client.post(reverse("question-list"), payload, format="json")
    assert fifth.status_code == 201
    assert fifth.data["position"] == 5

    sixth = auth_client.post(reverse("question-list"), payload, format="json")
    assert sixth.status_code == 400
    assert "activity" in sixth.data["errors"]


def test_standalone_question_create_appends_to_a_short_activity(
    auth_client, make_activity, teacher, classroom
):
    activity = make_activity(teacher, classroom, with_questions=False)
    response = auth_client.post(
        reverse("question-list"),
        {
            "activity": activity.pk,
            "prompt": "What does RAM stand for?",
            "question_type": QuestionType.SHORT_TEXT,
            "accepted_answers": ["Random Access Memory"],
        },
        format="json",
    )
    assert response.status_code == 201
    assert response.data["position"] == 1
