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


def test_questions_beyond_the_configured_cap_are_rejected(
    auth_client, classroom, settings
):
    settings.CARICUE = {**settings.CARICUE, "MAX_QUESTIONS_PER_ACTIVITY": 5}
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


def test_an_activity_can_hold_far_more_than_five_questions(auth_client, classroom):
    response = auth_client.post(
        reverse("activity-list"),
        {
            "classroom": classroom.pk,
            "title": "Long form",
            "questions": [mcq(f"Question {n}") for n in range(30)],
        },
        format="json",
    )
    assert response.status_code == 201
    assert len(response.data["questions"]) == 30
    assert [q["position"] for q in response.data["questions"]] == list(range(1, 31))


def _put_body(current: dict, questions: list[dict]) -> dict:
    return {
        "classroom": current["classroom"],
        "title": current["title"],
        "topic": current["topic"],
        "questions": questions,
    }


def test_editing_an_activity_keeps_questions_choices_and_responses(
    auth_client, activity, open_session, enrolled_students, answers_for
):
    from caricue.live.models import Participant, Response
    from caricue.live.services import submit_responses

    participant = Participant.objects.create(
        live_session=open_session, display_name="Amara"
    )
    submit_responses(
        session=open_session,
        participant=participant,
        answers=answers_for(activity),
    )
    responses_before = Response.objects.count()
    assert responses_before > 0
    question_ids = list(activity.questions.values_list("pk", flat=True))
    choice_ids = list(
        activity.questions.get(position=1).choices.values_list("pk", flat=True)
    )

    detail = reverse("activity-detail", args=[activity.pk])
    current = auth_client.get(detail).data
    current["questions"][0]["prompt"] = "Reworded prompt"
    current["questions"][0]["choices"][0]["text"] = "SSD"
    response = auth_client.put(
        detail, _put_body(current, current["questions"]), format="json"
    )

    assert response.status_code == 200
    assert list(activity.questions.values_list("pk", flat=True)) == question_ids
    assert Response.objects.count() == responses_before
    first = activity.questions.get(position=1)
    assert first.prompt == "Reworded prompt"
    assert list(first.choices.values_list("pk", flat=True)) == choice_ids
    assert first.choices.get(pk=choice_ids[0]).text == "SSD"
    # Existing answers still point at the (renamed) choice.
    assert Response.objects.filter(selected_choice_id=choice_ids[0]).exists()


def test_reordering_questions_keeps_identity_and_responses(
    auth_client, activity, open_session, answers_for
):
    from caricue.live.models import Participant, Response
    from caricue.live.services import submit_responses

    participant = Participant.objects.create(
        live_session=open_session, display_name="Kai"
    )
    submit_responses(
        session=open_session, participant=participant, answers=answers_for(activity)
    )
    total = Response.objects.count()
    by_prompt = {q.prompt: q.pk for q in activity.questions.all()}

    detail = reverse("activity-detail", args=[activity.pk])
    current = auth_client.get(detail).data
    reordered = list(reversed(current["questions"]))
    response = auth_client.put(detail, _put_body(current, reordered), format="json")

    assert response.status_code == 200
    assert Response.objects.count() == total
    for question in response.data["questions"]:
        assert by_prompt[question["prompt"]] == question["id"]
    assert [q["position"] for q in response.data["questions"]] == [1, 2, 3, 4]


def test_removing_a_question_deletes_only_that_question(auth_client, activity):
    detail = reverse("activity-detail", args=[activity.pk])
    current = auth_client.get(detail).data
    kept = current["questions"][:-1]
    removed_id = current["questions"][-1]["id"]

    response = auth_client.put(detail, _put_body(current, kept), format="json")

    assert response.status_code == 200
    ids = [q["id"] for q in response.data["questions"]]
    assert removed_id not in ids
    assert ids == [q["id"] for q in kept]


def test_a_foreign_question_id_in_the_payload_is_treated_as_new(
    auth_client, activity, make_activity, other_teacher, make_classroom
):
    other_activity = make_activity(other_teacher, make_classroom(other_teacher))
    foreign = other_activity.questions.first()
    detail = reverse("activity-detail", args=[activity.pk])
    current = auth_client.get(detail).data
    payload = [{**mcq("Smuggled"), "id": foreign.pk}]

    response = auth_client.put(detail, _put_body(current, payload), format="json")

    assert response.status_code == 200
    foreign.refresh_from_db()
    assert foreign.prompt != "Smuggled"
    assert foreign.activity_id == other_activity.pk
    assert response.data["questions"][0]["id"] != foreign.pk


def test_question_payload_reports_how_many_responses_it_holds(
    auth_client, activity, open_session, answers_for
):
    from caricue.live.models import Participant
    from caricue.live.services import submit_responses

    participant = Participant.objects.create(
        live_session=open_session, display_name="Lee"
    )
    submit_responses(
        session=open_session, participant=participant, answers=answers_for(activity)
    )
    detail = reverse("activity-detail", args=[activity.pk])
    questions = auth_client.get(detail).data["questions"]
    assert all(q["response_count"] == 1 for q in questions)


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
    auth_client, other_client, activity, settings
):
    settings.CARICUE = {**settings.CARICUE, "MAX_QUESTIONS_PER_ACTIVITY": 5}
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
