"""Deterministic scoring.

Correctness must be predictable. A teacher has to be able to look at their
accepted-answer list and know exactly what will be marked right.
"""

from __future__ import annotations

import pytest

from caricue.activities.models import (
    Activity,
    Choice,
    Question,
    QuestionType,
    normalize_text_answer,
)
from caricue.live.services import score_answer

pytestmark = pytest.mark.django_db


@pytest.fixture
def mcq(teacher, classroom) -> Question:
    activity = Activity.objects.create(
        teacher=teacher, classroom=classroom, title="Scoring"
    )
    question = Question.objects.create(
        activity=activity,
        position=1,
        prompt="Which device routes between networks?",
        question_type=QuestionType.MULTIPLE_CHOICE,
    )
    Choice.objects.create(question=question, text="Router", is_correct=True, position=1)
    Choice.objects.create(question=question, text="Switch", is_correct=False, position=2)
    return question


@pytest.fixture
def short_text(teacher, classroom):
    activity = Activity.objects.create(
        teacher=teacher, classroom=classroom, title="Short text"
    )

    def _make(accepted: list[str]) -> Question:
        return Question.objects.create(
            activity=activity,
            position=activity.questions.count() + 1,
            prompt="What does RAM stand for?",
            question_type=QuestionType.SHORT_TEXT,
            accepted_answers=accepted,
        )

    return _make


# --------------------------------------------------------------------------- #
# Normalisation
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Random Access Memory", "random access memory"),
        ("  Random Access Memory  ", "random access memory"),
        ("RANDOM ACCESS MEMORY", "random access memory"),
        ("Random   Access\tMemory", "random access memory"),
        ("Random\nAccess Memory", "random access memory"),
        ("", ""),
        ("   ", ""),
        (None, ""),
    ],
)
def test_normalisation_is_limited_to_whitespace_and_case(raw, expected):
    assert normalize_text_answer(raw) == expected


def test_normalisation_does_not_do_fuzzy_matching():
    """A misspelling stays wrong. No stemming, no edit distance, no guessing."""
    assert normalize_text_answer("Random Acess Memory") != normalize_text_answer(
        "Random Access Memory"
    )


# --------------------------------------------------------------------------- #
# Multiple choice
# --------------------------------------------------------------------------- #
def test_correct_choice_scores_true(mcq):
    correct = mcq.choices.get(is_correct=True)
    assert (
        score_answer(question=mcq, selected_choice_id=correct.pk, text_response="")
        is True
    )


def test_incorrect_choice_scores_false(mcq):
    wrong = mcq.choices.get(is_correct=False)
    assert (
        score_answer(question=mcq, selected_choice_id=wrong.pk, text_response="") is False
    )


def test_missing_choice_scores_false(mcq):
    assert score_answer(question=mcq, selected_choice_id=None, text_response="") is False


def test_a_choice_from_a_different_question_is_not_credited(mcq, short_text):
    """Scoring is scoped to the question, so a stray id cannot score true."""
    other = Question.objects.create(
        activity=mcq.activity,
        position=9,
        prompt="Another",
        question_type=QuestionType.MULTIPLE_CHOICE,
    )
    foreign = Choice.objects.create(
        question=other, text="Router", is_correct=True, position=1
    )
    assert (
        score_answer(question=mcq, selected_choice_id=foreign.pk, text_response="")
        is False
    )


def test_multiple_correct_choices_both_score_true(mcq):
    second = mcq.choices.get(is_correct=False)
    second.is_correct = True
    second.save(update_fields=["is_correct"])
    for choice in mcq.choices.all():
        assert (
            score_answer(question=mcq, selected_choice_id=choice.pk, text_response="")
            is True
        )


# --------------------------------------------------------------------------- #
# Short text
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "answer",
    [
        "Random Access Memory",
        "random access memory",
        "RANDOM ACCESS MEMORY",
        "  Random   Access Memory ",
    ],
)
def test_accepted_short_answers_score_true(short_text, answer):
    question = short_text(["Random Access Memory"])
    assert (
        score_answer(question=question, selected_choice_id=None, text_response=answer)
        is True
    )


@pytest.mark.parametrize(
    "answer", ["Read Access Memory", "RAM", "Random Acess Memory", ""]
)
def test_unaccepted_short_answers_score_false(short_text, answer):
    question = short_text(["Random Access Memory"])
    assert (
        score_answer(question=question, selected_choice_id=None, text_response=answer)
        is False
    )


def test_any_entry_in_the_accepted_list_scores_true(short_text):
    question = short_text(["Random Access Memory", "RAM"])
    for answer in ("random access memory", "ram", "RAM"):
        assert (
            score_answer(question=question, selected_choice_id=None, text_response=answer)
            is True
        )


def test_short_text_without_accepted_answers_is_not_scored(short_text):
    """Open-ended writing is never graded automatically in the MVP."""
    question = short_text([])
    result = score_answer(
        question=question,
        selected_choice_id=None,
        text_response="A switch is local and a router joins networks.",
    )
    assert result is None
    assert question.is_auto_scored is False


def test_blank_entries_in_the_accepted_list_are_ignored(short_text):
    question = short_text(["  ", "", "RAM"])
    assert question.normalized_accepted_answers() == ["ram"]
    assert (
        score_answer(question=question, selected_choice_id=None, text_response="")
        is False
    )


def test_non_string_accepted_answers_are_ignored(short_text):
    question = short_text(["RAM"])
    question.accepted_answers = ["RAM", 42, None]
    assert question.normalized_accepted_answers() == ["ram"]


def test_malformed_accepted_answers_do_not_crash_scoring(short_text):
    question = short_text(["RAM"])
    question.accepted_answers = "not-a-list"
    assert question.normalized_accepted_answers() == []
    assert (
        score_answer(question=question, selected_choice_id=None, text_response="ram")
        is None
    )


# --------------------------------------------------------------------------- #
# Confidence
# --------------------------------------------------------------------------- #
def test_confidence_questions_are_never_right_or_wrong(teacher, classroom):
    activity = Activity.objects.create(
        teacher=teacher, classroom=classroom, title="Confidence"
    )
    question = Question.objects.create(
        activity=activity,
        position=1,
        prompt="How confident are you?",
        question_type=QuestionType.CONFIDENCE,
    )
    assert (
        score_answer(question=question, selected_choice_id=None, text_response="") is None
    )
    assert question.is_auto_scored is False


# --------------------------------------------------------------------------- #
# End-to-end persistence of the score
# --------------------------------------------------------------------------- #
def test_submitted_responses_persist_their_correctness(
    api, open_session, activity, answers_for
):
    from caricue.live.models import Response

    joined = api.post(
        f"/api/public/sessions/{open_session.public_token}/join/",
        {"identifier": "Amara J"},
        format="json",
    )
    api.post(
        f"/api/public/sessions/{open_session.public_token}/submit/",
        {
            "participant_token": joined.data["participant_token"],
            "answers": answers_for(activity, correct=True),
        },
        format="json",
    )

    by_position = {
        response.question.position: response
        for response in Response.objects.select_related("question")
    }
    assert by_position[1].is_correct is True  # multiple choice
    assert by_position[2].is_correct is True  # accepted short answer
    assert by_position[3].is_correct is None  # open-ended, not scored
    assert by_position[4].is_correct is None  # confidence scale


def test_wrong_answers_persist_as_incorrect(api, open_session, activity, answers_for):
    from caricue.live.models import Response

    joined = api.post(
        f"/api/public/sessions/{open_session.public_token}/join/",
        {"identifier": "Devon C"},
        format="json",
    )
    api.post(
        f"/api/public/sessions/{open_session.public_token}/submit/",
        {
            "participant_token": joined.data["participant_token"],
            "answers": answers_for(activity, correct=False),
        },
        format="json",
    )

    by_position = {
        response.question.position: response
        for response in Response.objects.select_related("question")
    }
    assert by_position[1].is_correct is False
    assert by_position[2].is_correct is False
