"""Deterministic misconception cards from session insight facts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from django.conf import settings

from caricue.activities.models import QuestionType
from caricue.insights.service import QuestionInsight, SessionInsights


@dataclass
class MisconceptionFact:
    kind: str = "fact"
    label: str = ""
    value: str | int | float = ""


@dataclass
class MisconceptionSuggestion:
    kind: str = "suggestion"
    title: str = ""
    body: str = ""
    requires_teacher_review: bool = True


@dataclass
class MisconceptionCard:
    question_id: int
    position: int
    prompt: str
    question_type: str
    correctness_percentage: float
    high_confidence_wrong_count: int = 0
    facts: list[MisconceptionFact] = field(default_factory=list)
    suggestion: MisconceptionSuggestion | None = None

    def as_dict(self) -> dict:
        payload = asdict(self)
        if self.suggestion is not None:
            payload["suggestion"] = asdict(self.suggestion)
        return payload


def build_misconception_cards(insights: SessionInsights) -> list[MisconceptionCard]:
    """Return up to three misconception cards ranked by severity."""
    low_threshold = settings.CARICUE["LOW_CORRECTNESS_THRESHOLD"]
    hc_wrong_by_question = _high_confidence_wrong_counts(insights)

    candidates: list[tuple[float, MisconceptionCard]] = []
    for question in insights.questions:
        if (
            question.correctness_percentage is None
            or question.response_count == 0
            or question.correctness_percentage >= low_threshold
            or not question.is_auto_scored
        ):
            continue

        hc_count = hc_wrong_by_question.get(question.question_id, 0)
        card = _card_for_question(question, hc_count, low_threshold)
        severity = _severity_score(question, hc_count, low_threshold)
        candidates.append((severity, card))

    candidates.sort(key=lambda item: item[0], reverse=True)
    return [card for _, card in candidates[:3]]


def _high_confidence_wrong_counts(insights: SessionInsights) -> dict[int, int]:
    counts: dict[int, int] = {}
    for item in insights.high_confidence_incorrect:
        qid = _question_id_for_signal(insights, item.question_position)
        if qid is not None:
            counts[qid] = counts.get(qid, 0) + 1
    return counts


def _question_id_for_signal(insights: SessionInsights, position: int) -> int | None:
    for question in insights.questions:
        if question.position == position:
            return question.question_id
    return None


def _severity_score(
    question: QuestionInsight, hc_count: int, low_threshold: float
) -> float:
    below = max(0.0, low_threshold - (question.correctness_percentage or 0))
    incorrect_pct = 100.0 - (question.correctness_percentage or 0)
    return below * 10 + hc_count * 5 + incorrect_pct


def _card_for_question(
    question: QuestionInsight, hc_count: int, low_threshold: float
) -> MisconceptionCard:
    facts: list[MisconceptionFact] = [
        MisconceptionFact(
            label="Correctness",
            value=f"{question.correctness_percentage:.0f}%",
        ),
        MisconceptionFact(
            label="Responses",
            value=question.response_count,
        ),
    ]
    if hc_count:
        facts.append(
            MisconceptionFact(
                label="High-confidence wrong",
                value=hc_count,
            )
        )

    suggestion_body = (
        f"Only {question.correctness_percentage:.0f}% answered question "
        f"{question.position} correctly. Consider reteaching this point "
        "before moving on."
    )

    if question.question_type == QuestionType.MULTIPLE_CHOICE:
        top_distractor = max(
            (c for c in question.choice_breakdown if not c.is_correct),
            key=lambda c: c.count,
            default=None,
        )
        if top_distractor is not None and top_distractor.count > 0:
            facts.append(
                MisconceptionFact(
                    label="Top wrong choice",
                    value=f'"{top_distractor.text}" ({top_distractor.percentage:.0f}%)',
                )
            )
            suggestion_body += (
                f' The most common wrong choice was "{top_distractor.text}" '
                f"({top_distractor.percentage:.0f}%), which points at a "
                "specific misconception rather than a random guess."
            )
    elif question.question_type == QuestionType.SHORT_TEXT:
        wrong_answers = [
            entry
            for entry in question.common_answers
            if entry.get("matches_accepted") is False
        ]
        if wrong_answers:
            top = wrong_answers[0]
            facts.append(
                MisconceptionFact(
                    label="Common wrong answer",
                    value=f'"{top["answer"]}" ({top["percentage"]:.0f}%)',
                )
            )
            suggestion_body += (
                f' A common wrong answer was "{top["answer"]}" '
                f"({top['percentage']:.0f}%)."
            )

    return MisconceptionCard(
        question_id=question.question_id,
        position=question.position,
        prompt=question.prompt,
        question_type=question.question_type,
        correctness_percentage=question.correctness_percentage or 0,
        high_confidence_wrong_count=hc_count,
        facts=facts,
        suggestion=MisconceptionSuggestion(
            title=f"Reteach question {question.position}",
            body=suggestion_body,
        ),
    )
