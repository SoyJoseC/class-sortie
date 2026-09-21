"""Deterministic insight calculation.

Everything in this module is arithmetic over stored responses. No model, no
heuristic guessing, no LLM. The output is labelled ``"kind": "fact"`` at the
API boundary so the UI can present it differently from AI suggestions, which
are produced separately in `providers.py`.

Open-ended answers are never graded here. A short-text question is only
scored when the teacher supplied accepted answers, and the comparison is the
transparent normalisation in `activities.models.normalize_text_answer`.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field

from django.conf import settings
from django.db.models import Prefetch

from caricue.activities.models import Question, QuestionType, normalize_text_answer
from caricue.live.models import LiveSession, Participant, Response


@dataclass
class ChoiceBreakdown:
    choice_id: int
    text: str
    is_correct: bool
    count: int
    percentage: float


@dataclass
class QuestionInsight:
    question_id: int
    position: int
    prompt: str
    question_type: str
    is_auto_scored: bool
    response_count: int
    correct_count: int
    incorrect_count: int
    correctness_percentage: float | None
    choice_breakdown: list[ChoiceBreakdown] = field(default_factory=list)
    common_answers: list[dict] = field(default_factory=list)
    confidence_distribution: dict[str, int] = field(default_factory=dict)
    average_confidence: float | None = None


@dataclass
class AttentionItem:
    participant_id: int
    label: str
    reasons: list[str]
    score_percentage: float | None
    average_confidence: float | None


@dataclass
class SignalItem:
    participant_id: int
    label: str
    question_position: int
    question_prompt: str
    confidence_value: int


@dataclass
class SessionInsights:
    session_id: int
    session_code: str
    session_status: str
    activity_title: str
    activity_topic: str
    classroom_name: str
    roster_size: int
    participant_count: int
    submitted_count: int
    completion_percentage: float | None
    auto_scored_response_count: int
    overall_correctness_percentage: float | None
    confidence_distribution: dict[str, int]
    average_confidence: float | None
    questions: list[QuestionInsight]
    lowest_correctness_questions: list[dict]
    high_confidence_incorrect: list[SignalItem]
    low_confidence_correct: list[SignalItem]
    needs_attention: list[AttentionItem]
    has_confidence_data: bool
    has_auto_scored_data: bool

    def as_dict(self) -> dict:
        return asdict(self)


def _percentage(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator * 100 / denominator, 1)


def build_session_insights(session: LiveSession) -> SessionInsights:
    """Computes every deterministic figure for one session in a few queries."""
    questions = list(
        session.activity.questions.prefetch_related("choices").order_by("position")
    )
    participants = list(
        session.participants.select_related("student").prefetch_related(
            Prefetch(
                "responses",
                queryset=Response.objects.select_related("question", "selected_choice"),
            )
        )
    )

    responses: list[Response] = [
        response
        for participant in participants
        for response in participant.responses.all()
    ]
    responses_by_question: dict[int, list[Response]] = {q.pk: [] for q in questions}
    for response in responses:
        responses_by_question.setdefault(response.question_id, []).append(response)

    submitted = [p for p in participants if p.has_submitted]
    roster_size = session.roster_size

    question_insights = [
        _build_question_insight(question, responses_by_question.get(question.pk, []))
        for question in questions
    ]

    auto_scored = [r for r in responses if r.is_correct is not None]
    correct_total = sum(1 for r in auto_scored if r.is_correct)

    confidence_values = [
        r.confidence_value for r in responses if r.confidence_value is not None
    ]
    confidence_distribution = _confidence_distribution(confidence_values)

    scored_questions = [
        qi for qi in question_insights if qi.correctness_percentage is not None
    ]
    low_threshold = settings.CARICUE["LOW_CORRECTNESS_THRESHOLD"]
    lowest = sorted(
        (qi for qi in scored_questions if qi.response_count > 0),
        key=lambda qi: (qi.correctness_percentage, qi.position),
    )
    lowest_correctness_questions = [
        {
            "question_id": qi.question_id,
            "position": qi.position,
            "prompt": qi.prompt,
            "correctness_percentage": qi.correctness_percentage,
            "below_threshold": qi.correctness_percentage < low_threshold,
        }
        for qi in lowest[:3]
    ]

    high_conf_threshold = settings.CARICUE["HIGH_CONFIDENCE_THRESHOLD"]
    low_conf_threshold = settings.CARICUE["LOW_CONFIDENCE_THRESHOLD"]

    high_confidence_incorrect = [
        _signal_item(r)
        for r in responses
        if r.is_correct is False
        and r.confidence_value is not None
        and r.confidence_value >= high_conf_threshold
    ]
    low_confidence_correct = [
        _signal_item(r)
        for r in responses
        if r.is_correct is True
        and r.confidence_value is not None
        and r.confidence_value <= low_conf_threshold
    ]

    return SessionInsights(
        session_id=session.pk,
        session_code=session.code,
        session_status=session.status,
        activity_title=session.activity.title,
        activity_topic=session.activity.topic,
        classroom_name=session.classroom.name,
        roster_size=roster_size,
        participant_count=len(participants),
        submitted_count=len(submitted),
        # Only meaningful when the class has a roster to compare against.
        completion_percentage=(
            _percentage(len(submitted), roster_size) if roster_size > 0 else None
        ),
        auto_scored_response_count=len(auto_scored),
        overall_correctness_percentage=(
            _percentage(correct_total, len(auto_scored)) if auto_scored else None
        ),
        confidence_distribution=confidence_distribution,
        average_confidence=(
            round(sum(confidence_values) / len(confidence_values), 2)
            if confidence_values
            else None
        ),
        questions=question_insights,
        lowest_correctness_questions=lowest_correctness_questions,
        high_confidence_incorrect=high_confidence_incorrect,
        low_confidence_correct=low_confidence_correct,
        needs_attention=_needs_attention(participants, high_conf_threshold),
        has_confidence_data=bool(confidence_values),
        has_auto_scored_data=bool(auto_scored),
    )


def _build_question_insight(
    question: Question, responses: list[Response]
) -> QuestionInsight:
    response_count = len(responses)
    scored = [r for r in responses if r.is_correct is not None]
    correct_count = sum(1 for r in scored if r.is_correct)
    incorrect_count = len(scored) - correct_count

    choice_breakdown: list[ChoiceBreakdown] = []
    if question.question_type == QuestionType.MULTIPLE_CHOICE:
        counts = Counter(
            r.selected_choice_id for r in responses if r.selected_choice_id is not None
        )
        answered = sum(counts.values())
        for choice in question.choices.all():
            count = counts.get(choice.pk, 0)
            choice_breakdown.append(
                ChoiceBreakdown(
                    choice_id=choice.pk,
                    text=choice.text,
                    is_correct=choice.is_correct,
                    count=count,
                    percentage=_percentage(count, answered),
                )
            )

    common_answers: list[dict] = []
    if question.question_type == QuestionType.SHORT_TEXT:
        accepted = set(question.normalized_accepted_answers())
        counter = Counter(
            normalize_text_answer(r.text_response)
            for r in responses
            if normalize_text_answer(r.text_response)
        )
        limit = settings.CARICUE["COMMON_ANSWER_LIMIT"]
        # Representative raw text keeps the teacher's view readable while the
        # grouping stays on the normalised key.
        examples: dict[str, str] = {}
        for r in responses:
            key = normalize_text_answer(r.text_response)
            if key and key not in examples:
                examples[key] = r.text_response.strip()
        common_answers = [
            {
                "answer": examples.get(key, key),
                "normalized": key,
                "count": count,
                "percentage": _percentage(count, response_count),
                "matches_accepted": key in accepted if accepted else None,
            }
            for key, count in counter.most_common(limit)
        ]

    confidence_values = [
        r.confidence_value for r in responses if r.confidence_value is not None
    ]

    return QuestionInsight(
        question_id=question.pk,
        position=question.position,
        prompt=question.prompt,
        question_type=question.question_type,
        is_auto_scored=question.is_auto_scored,
        response_count=response_count,
        correct_count=correct_count,
        incorrect_count=incorrect_count,
        correctness_percentage=(
            _percentage(correct_count, len(scored)) if scored else None
        ),
        choice_breakdown=choice_breakdown,
        common_answers=common_answers,
        confidence_distribution=_confidence_distribution(confidence_values),
        average_confidence=(
            round(sum(confidence_values) / len(confidence_values), 2)
            if confidence_values
            else None
        ),
    )


def _confidence_distribution(values: list[int]) -> dict[str, int]:
    counter = Counter(values)
    return {str(level): counter.get(level, 0) for level in range(1, 6)}


def _signal_item(response: Response) -> SignalItem:
    return SignalItem(
        participant_id=response.participant_id,
        label=response.participant.label,
        question_position=response.question.position,
        question_prompt=response.question.prompt,
        confidence_value=response.confidence_value,
    )


def _needs_attention(
    participants: list[Participant], high_conf_threshold: int
) -> list[AttentionItem]:
    """Participants a teacher may want to check in with.

    Deterministic rules only, and each item carries the reasons that triggered
    it so the teacher can judge for themselves rather than trusting a score.
    """
    score_threshold = settings.CARICUE["ATTENTION_SCORE_THRESHOLD"]
    items: list[AttentionItem] = []

    for participant in participants:
        responses = list(participant.responses.all())
        scored = [r for r in responses if r.is_correct is not None]
        correct = sum(1 for r in scored if r.is_correct)
        score = _percentage(correct, len(scored)) if scored else None
        confidences = [
            r.confidence_value for r in responses if r.confidence_value is not None
        ]
        average_confidence = (
            round(sum(confidences) / len(confidences), 2) if confidences else None
        )

        reasons: list[str] = []
        if not participant.has_submitted:
            reasons.append("Joined but has not submitted")
        if score is not None and score < score_threshold:
            reasons.append(f"Scored {score:.0f}% on auto-scored questions")

        overconfident = sum(
            1
            for r in responses
            if r.is_correct is False
            and r.confidence_value is not None
            and r.confidence_value >= high_conf_threshold
        )
        if overconfident:
            reasons.append(f"Confident but incorrect on {overconfident} question(s)")

        if reasons:
            items.append(
                AttentionItem(
                    participant_id=participant.pk,
                    label=participant.label,
                    reasons=reasons,
                    score_percentage=score,
                    average_confidence=average_confidence,
                )
            )

    items.sort(
        key=lambda item: (item.score_percentage is None, item.score_percentage or 0)
    )
    return items
