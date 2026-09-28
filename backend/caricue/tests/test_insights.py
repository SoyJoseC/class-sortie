"""Insight calculations and the provider abstraction."""

from __future__ import annotations

import pytest
from django.urls import reverse

from caricue.activities.models import QuestionType
from caricue.insights.providers import (
    BaseInsightProvider,
    LLMInsightProvider,
    RuleBasedInsightProvider,
    generate_suggestions,
    get_insight_provider,
)
from caricue.insights.service import build_session_insights
from caricue.live.services import join_session, submit_responses

pytestmark = pytest.mark.django_db


def submit(session, activity, identifier: str, answers: list[dict]):
    result = join_session(session=session, identifier=identifier)
    return submit_responses(
        session=session, participant=result.participant, answers=answers
    )


def answer_set(activity, *, mcq_correct: bool, confidence: int, ram_correct: bool = True):
    """Builds a full answer payload with explicit correctness and confidence."""
    payload = []
    for question in activity.questions.prefetch_related("choices").order_by("position"):
        if question.question_type == QuestionType.MULTIPLE_CHOICE:
            # The fixture has one correct choice and two distractors; pick the
            # first matching one so the payload is deterministic.
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


# --------------------------------------------------------------------------- #
# Participation and completion
# --------------------------------------------------------------------------- #
def test_empty_session_reports_zeroes_without_dividing_by_zero(open_session):
    insights = build_session_insights(open_session)

    assert insights.participant_count == 0
    assert insights.submitted_count == 0
    assert insights.completion_percentage == 0.0
    assert insights.overall_correctness_percentage is None
    assert insights.average_confidence is None
    assert insights.has_auto_scored_data is False
    assert insights.needs_attention == []


def test_participation_and_completion_use_the_active_roster(open_session, activity):
    submit(
        open_session,
        activity,
        "Amara J",
        answer_set(activity, mcq_correct=True, confidence=4),
    )
    submit(
        open_session,
        activity,
        "Devon C",
        answer_set(activity, mcq_correct=True, confidence=4),
    )

    insights = build_session_insights(open_session)
    assert insights.roster_size == 4
    assert insights.participant_count == 2
    assert insights.submitted_count == 2
    assert insights.completion_percentage == 50.0


def test_completion_is_none_when_the_class_has_no_roster(
    auth_client, make_classroom, make_activity, teacher
):
    """Without a roster there is no honest denominator, so we report nothing."""
    from caricue.live.services import launch_session

    classroom = make_classroom(teacher, "No roster")
    activity = make_activity(teacher, classroom)
    session, _ = launch_session(activity=activity)

    submit(
        session, activity, "Amara J", answer_set(activity, mcq_correct=True, confidence=4)
    )
    insights = build_session_insights(session)

    assert insights.roster_size == 0
    assert insights.completion_percentage is None
    assert insights.submitted_count == 1


def test_a_joined_but_unsubmitted_participant_counts_separately(open_session, activity):
    join_session(session=open_session, identifier="Lurker")
    submit(
        open_session,
        activity,
        "Amara J",
        answer_set(activity, mcq_correct=True, confidence=4),
    )

    insights = build_session_insights(open_session)
    assert insights.participant_count == 2
    assert insights.submitted_count == 1


# --------------------------------------------------------------------------- #
# Correctness
# --------------------------------------------------------------------------- #
def test_correctness_by_question_and_overall(open_session, activity):
    submit(
        open_session, activity, "A", answer_set(activity, mcq_correct=True, confidence=4)
    )
    submit(
        open_session, activity, "B", answer_set(activity, mcq_correct=True, confidence=4)
    )
    submit(
        open_session, activity, "C", answer_set(activity, mcq_correct=False, confidence=2)
    )
    submit(
        open_session, activity, "D", answer_set(activity, mcq_correct=False, confidence=2)
    )

    insights = build_session_insights(open_session)
    by_position = {q.position: q for q in insights.questions}

    assert by_position[1].correctness_percentage == 50.0
    assert by_position[1].correct_count == 2
    assert by_position[1].incorrect_count == 2
    assert by_position[2].correctness_percentage == 100.0

    # 8 scored responses across two scored questions: 6 correct.
    assert insights.auto_scored_response_count == 8
    assert insights.overall_correctness_percentage == 75.0


def test_unscored_questions_report_no_correctness_percentage(open_session, activity):
    submit(
        open_session, activity, "A", answer_set(activity, mcq_correct=True, confidence=4)
    )
    insights = build_session_insights(open_session)
    by_position = {q.position: q for q in insights.questions}

    assert by_position[3].correctness_percentage is None  # open-ended
    assert by_position[3].is_auto_scored is False
    assert by_position[4].correctness_percentage is None  # confidence scale


def test_choice_breakdown_shows_the_distractor_distribution(open_session, activity):
    submit(
        open_session, activity, "A", answer_set(activity, mcq_correct=True, confidence=4)
    )
    submit(
        open_session, activity, "B", answer_set(activity, mcq_correct=False, confidence=4)
    )

    insights = build_session_insights(open_session)
    breakdown = {c.text: c for c in insights.questions[0].choice_breakdown}

    assert breakdown["Solid-state drive"].count == 1
    assert breakdown["Solid-state drive"].is_correct is True
    assert breakdown["RAM"].count == 1
    assert breakdown["RAM"].percentage == 50.0
    # Choices nobody picked are still listed, so gaps are visible.
    assert breakdown["CPU cache"].count == 0


# --------------------------------------------------------------------------- #
# Confidence
# --------------------------------------------------------------------------- #
def test_confidence_distribution_covers_the_whole_scale(open_session, activity):
    submit(
        open_session, activity, "A", answer_set(activity, mcq_correct=True, confidence=5)
    )
    submit(
        open_session, activity, "B", answer_set(activity, mcq_correct=True, confidence=5)
    )
    submit(
        open_session, activity, "C", answer_set(activity, mcq_correct=True, confidence=1)
    )

    insights = build_session_insights(open_session)
    # Two responses per student carry confidence: the MCQ and the scale item.
    assert insights.confidence_distribution == {"1": 2, "2": 0, "3": 0, "4": 0, "5": 4}
    assert insights.has_confidence_data is True
    assert insights.average_confidence == pytest.approx(3.67, abs=0.01)


def test_no_confidence_data_is_reported_as_absent(open_session, activity):
    """An activity that never asks for confidence must not fake a distribution."""
    activity.questions.filter(question_type=QuestionType.CONFIDENCE).delete()
    activity.questions.filter(collect_confidence=True).update(collect_confidence=False)
    activity.refresh_from_db()

    submit(
        open_session, activity, "A", answer_set(activity, mcq_correct=True, confidence=4)
    )

    insights = build_session_insights(open_session)
    assert insights.has_confidence_data is False
    assert insights.average_confidence is None
    assert insights.confidence_distribution == {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}


# --------------------------------------------------------------------------- #
# Performance-versus-confidence signals
# --------------------------------------------------------------------------- #
def test_high_confidence_incorrect_is_surfaced(open_session, activity):
    submit(
        open_session,
        activity,
        "Overconfident",
        answer_set(activity, mcq_correct=False, confidence=5),
    )

    insights = build_session_insights(open_session)
    assert len(insights.high_confidence_incorrect) == 1
    signal = insights.high_confidence_incorrect[0]
    assert signal.label == "Overconfident"
    assert signal.confidence_value == 5
    assert signal.question_position == 1


def test_low_confidence_correct_is_surfaced(open_session, activity):
    submit(
        open_session,
        activity,
        "Unsure",
        answer_set(activity, mcq_correct=True, confidence=1),
    )

    insights = build_session_insights(open_session)
    assert len(insights.low_confidence_correct) == 1
    assert insights.low_confidence_correct[0].label == "Unsure"


def test_a_correct_confident_answer_raises_no_signal(open_session, activity):
    submit(
        open_session,
        activity,
        "Solid",
        answer_set(activity, mcq_correct=True, confidence=5),
    )

    insights = build_session_insights(open_session)
    assert insights.high_confidence_incorrect == []
    assert insights.low_confidence_correct == []


# --------------------------------------------------------------------------- #
# Lowest correctness and attention list
# --------------------------------------------------------------------------- #
def test_lowest_correctness_questions_are_ranked_and_flagged(open_session, activity):
    submit(
        open_session,
        activity,
        "A",
        answer_set(activity, mcq_correct=False, confidence=3, ram_correct=True),
    )
    submit(
        open_session,
        activity,
        "B",
        answer_set(activity, mcq_correct=False, confidence=3, ram_correct=True),
    )

    insights = build_session_insights(open_session)
    lowest = insights.lowest_correctness_questions

    assert lowest[0]["position"] == 1
    assert lowest[0]["correctness_percentage"] == 0.0
    assert lowest[0]["below_threshold"] is True
    assert lowest[-1]["below_threshold"] is False


def test_needs_attention_lists_low_scores_with_reasons(open_session, activity):
    submit(
        open_session,
        activity,
        "Struggling",
        answer_set(activity, mcq_correct=False, confidence=3, ram_correct=False),
    )
    submit(
        open_session,
        activity,
        "Doing well",
        answer_set(activity, mcq_correct=True, confidence=4, ram_correct=True),
    )

    insights = build_session_insights(open_session)
    labels = [item.label for item in insights.needs_attention]

    assert "Struggling" in labels
    assert "Doing well" not in labels
    item = next(i for i in insights.needs_attention if i.label == "Struggling")
    assert item.score_percentage == 0.0
    assert any("Scored" in reason for reason in item.reasons)


def test_needs_attention_flags_a_participant_who_never_submitted(open_session, activity):
    join_session(session=open_session, identifier="Joined only")
    insights = build_session_insights(open_session)

    item = next(i for i in insights.needs_attention if i.label == "Joined only")
    assert "has not submitted" in " ".join(item.reasons).lower()


def test_needs_attention_flags_confident_mistakes_even_at_a_decent_score(
    open_session, activity
):
    submit(
        open_session,
        activity,
        "Confidently wrong",
        answer_set(activity, mcq_correct=False, confidence=5, ram_correct=True),
    )
    insights = build_session_insights(open_session)

    item = next(i for i in insights.needs_attention if i.label == "Confidently wrong")
    assert any("Confident but incorrect" in reason for reason in item.reasons)


# --------------------------------------------------------------------------- #
# Short-text aggregation
# --------------------------------------------------------------------------- #
def test_common_short_answers_group_by_normalised_text(open_session, activity):
    short_text = activity.questions.get(position=2)

    for index, text in enumerate(
        [
            "Random Access Memory",
            "random access memory",
            "  RANDOM   ACCESS MEMORY  ",
            "Read Access Memory",
        ]
    ):
        result = join_session(session=open_session, identifier=f"Student {index}")
        answers = answer_set(activity, mcq_correct=True, confidence=4)
        for answer in answers:
            if answer["question"] == short_text.pk:
                answer["text_response"] = text
        submit_responses(
            session=open_session, participant=result.participant, answers=answers
        )

    insights = build_session_insights(open_session)
    common = {a["normalized"]: a for a in insights.questions[1].common_answers}

    assert common["random access memory"]["count"] == 3
    assert common["random access memory"]["percentage"] == 75.0
    assert common["random access memory"]["matches_accepted"] is True
    assert common["read access memory"]["matches_accepted"] is False
    # The displayed text is a real student answer, not the normalised key.
    assert common["random access memory"]["answer"] == "Random Access Memory"


def test_unscored_open_text_still_gets_grouped_for_reading(open_session, activity):
    open_question = activity.questions.get(position=3)
    for index in range(2):
        result = join_session(session=open_session, identifier=f"Student {index}")
        answers = answer_set(activity, mcq_correct=True, confidence=4)
        for answer in answers:
            if answer["question"] == open_question.pk:
                answer["text_response"] = "switch is local"
        submit_responses(
            session=open_session, participant=result.participant, answers=answers
        )

    insights = build_session_insights(open_session)
    common = insights.questions[2].common_answers

    assert common[0]["count"] == 2
    # No accepted list, so we make no claim about correctness.
    assert common[0]["matches_accepted"] is None


# --------------------------------------------------------------------------- #
# Dashboard endpoint
# --------------------------------------------------------------------------- #
def test_dashboard_separates_facts_from_suggestions(auth_client, open_session, activity):
    submit(
        open_session, activity, "A", answer_set(activity, mcq_correct=False, confidence=5)
    )

    response = auth_client.get(reverse("livesession-dashboard", args=[open_session.pk]))
    assert response.status_code == 200

    assert response.data["facts"]["kind"] == "fact"
    assert response.data["facts"]["submitted_count"] == 1
    assert 3 <= response.data["poll_interval_seconds"] <= 5

    assert response.data["suggestions"]
    for suggestion in response.data["suggestions"]:
        # Advisory, attributed, and never auto-applied.
        assert suggestion["kind"] == "suggestion"
        assert suggestion["requires_teacher_review"] is True
        assert suggestion["source"]


def test_dashboard_skips_suggestions_before_any_submission(auth_client, open_session):
    response = auth_client.get(reverse("livesession-dashboard", args=[open_session.pk]))
    assert response.data["suggestions"] == []
    assert response.data["facts"]["participant_count"] == 0


def test_results_endpoint_includes_participant_detail(
    auth_client, open_session, activity
):
    submit(
        open_session,
        activity,
        "Amara J",
        answer_set(activity, mcq_correct=True, confidence=4),
    )

    response = auth_client.get(reverse("livesession-results", args=[open_session.pk]))
    assert response.status_code == 200

    participant = response.data["participants"][0]
    assert participant["label"] == "Amara J"
    assert participant["display_name"] == "Amara J"
    assert participant["has_submitted"] is True
    assert len(participant["responses"]) == 4
    assert participant["responses"][0]["question_position"] == 1


# --------------------------------------------------------------------------- #
# Providers
# --------------------------------------------------------------------------- #
def test_rule_based_provider_is_the_default(settings):
    assert isinstance(get_insight_provider(), RuleBasedInsightProvider)


def test_rule_based_provider_needs_no_api_key(settings, open_session, activity):
    settings.INSIGHT_LLM_API_KEY = ""
    submit(
        open_session, activity, "A", answer_set(activity, mcq_correct=False, confidence=5)
    )

    suggestions = generate_suggestions(build_session_insights(open_session))
    assert suggestions
    assert all(s["source"] == "CariCue rules" for s in suggestions)


def test_rule_based_provider_flags_a_weak_question(open_session, activity):
    for name in ("A", "B", "C"):
        submit(
            open_session,
            activity,
            name,
            answer_set(activity, mcq_correct=False, confidence=5),
        )

    suggestions = generate_suggestions(build_session_insights(open_session))
    titles = " ".join(s["title"] for s in suggestions)
    bodies = " ".join(s["body"] for s in suggestions)

    assert "Reteach question 1" in titles
    assert "Confident misconceptions" in titles
    assert "RAM" in bodies or "wrong choice" in bodies


def test_rule_based_provider_says_move_on_when_the_class_is_strong(
    open_session, activity
):
    for name in ("A", "B", "C"):
        submit(
            open_session,
            activity,
            name,
            answer_set(activity, mcq_correct=True, confidence=4),
        )

    suggestions = generate_suggestions(build_session_insights(open_session))
    assert any("ready to move on" in s["title"] for s in suggestions)


def test_provider_always_suggests_a_next_lesson_question(open_session, activity):
    submit(
        open_session, activity, "A", answer_set(activity, mcq_correct=True, confidence=4)
    )
    suggestions = generate_suggestions(build_session_insights(open_session))
    assert any(s["category"] == "next_question" for s in suggestions)


def test_llm_provider_is_skipped_without_an_api_key(settings, open_session, activity):
    settings.INSIGHT_PROVIDER = "caricue.insights.providers.LLMInsightProvider"
    settings.INSIGHT_LLM_API_KEY = ""

    # Falls back to rules rather than returning nothing.
    assert isinstance(get_insight_provider(), RuleBasedInsightProvider)


def test_llm_provider_runs_when_configured(settings, open_session, activity):
    settings.INSIGHT_PROVIDER = "caricue.insights.providers.LLMInsightProvider"
    settings.INSIGHT_LLM_API_KEY = "test-key"

    provider = get_insight_provider()
    assert isinstance(provider, LLMInsightProvider)

    submit(
        open_session, activity, "A", answer_set(activity, mcq_correct=False, confidence=5)
    )
    suggestions = generate_suggestions(build_session_insights(open_session))

    assert suggestions
    for suggestion in suggestions:
        assert suggestion["kind"] == "suggestion"
        assert suggestion["requires_teacher_review"] is True
        assert "AI assistant" in suggestion["source"]


def test_redacted_prompt_excludes_student_identities(
    open_session, activity, enrolled_students
):
    """Nothing identifying may cross the boundary to an external model."""
    student = enrolled_students[0]
    result = join_session(session=open_session, identifier=student.display_name)
    submit_responses(
        session=open_session,
        participant=result.participant,
        answers=answer_set(activity, mcq_correct=False, confidence=5),
    )

    insights = build_session_insights(open_session)
    payload = BaseInsightProvider.build_redacted_prompt_payload(insights)
    serialized = str(payload)

    assert student.display_name not in serialized
    assert student.school_identifier not in serialized
    assert activity.teacher.email not in serialized
    assert open_session.classroom.name not in serialized
    assert "participant_id" not in serialized
    # The pedagogical signal survives redaction.
    assert payload["topic"]
    assert payload["questions"][0]["correctness_percentage"] == 0.0


def test_a_broken_provider_degrades_to_no_suggestions(settings, open_session, activity):
    settings.INSIGHT_PROVIDER = "caricue.insights.providers.DoesNotExist"
    submit(
        open_session, activity, "A", answer_set(activity, mcq_correct=True, confidence=4)
    )

    # Misconfiguration must not take the dashboard down.
    assert isinstance(get_insight_provider(), RuleBasedInsightProvider)
    assert generate_suggestions(build_session_insights(open_session))


def test_a_raising_llm_client_returns_no_suggestions(settings, open_session, activity):
    class Exploding:
        def summarize(self, payload):
            raise RuntimeError("upstream timeout")

    settings.INSIGHT_LLM_API_KEY = "test-key"
    provider = LLMInsightProvider(client=Exploding())
    submit(
        open_session, activity, "A", answer_set(activity, mcq_correct=True, confidence=4)
    )

    assert provider.generate(build_session_insights(open_session)) == []
