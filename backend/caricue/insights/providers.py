"""Suggestion providers.

Separation of concerns that matters here: `service.py` produces *facts* by
arithmetic; a provider produces *suggestions*, which are advisory and always
labelled as such.

Guarantees that hold for every provider, including future LLM-backed ones:

* The rule-based provider is the default and needs no API key.
* A suggestion never assigns a grade, never writes to student records, and
  never triggers an action. It is text a teacher may read and ignore.
* Prompts are built by `build_redacted_prompt_payload`, which excludes names,
  emails and roster identifiers. Only aggregates and anonymous answer text
  cross the boundary to an external model.
* A provider failure degrades to no suggestions; it never breaks a dashboard.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from typing import Any

from django.conf import settings
from django.utils.module_loading import import_string

from .service import SessionInsights

logger = logging.getLogger("caricue.insights")


@dataclass
class Suggestion:
    """One advisory item shown to the teacher.

    `kind` is always ``"suggestion"``. Deterministic figures are delivered
    separately and marked ``"fact"``, so the UI can keep the two visually
    distinct without inspecting content.
    """

    title: str
    body: str
    category: str  # misconception | follow_up | next_question | summary
    source: str  # provider label, shown in the UI
    requires_teacher_review: bool = True
    kind: str = "suggestion"

    def as_dict(self) -> dict:
        return asdict(self)


class BaseInsightProvider(ABC):
    """Interface every suggestion provider implements."""

    #: Human-readable label shown next to suggestions in the UI.
    name: str = "provider"
    #: False when the provider cannot run (e.g. missing API key).
    requires_api_key: bool = False

    def is_available(self) -> bool:
        return True

    @abstractmethod
    def generate(self, insights: SessionInsights) -> list[Suggestion]:
        """Returns suggestions for one session. Must never raise."""

    # -- prompt hygiene ---------------------------------------------------- #
    @staticmethod
    def build_redacted_prompt_payload(insights: SessionInsights) -> dict[str, Any]:
        """The only data a provider may send to an external service.

        Deliberately excludes participant labels, student names, emails and
        roster identifiers. Short-text answers are included because they are
        the pedagogical signal, but they arrive detached from any identity.
        """
        return {
            "topic": insights.activity_topic or insights.activity_title,
            "submitted_count": insights.submitted_count,
            "overall_correctness_percentage": insights.overall_correctness_percentage,
            "average_confidence": insights.average_confidence,
            "confidence_distribution": insights.confidence_distribution,
            "questions": [
                {
                    "position": question.position,
                    "prompt": question.prompt,
                    "question_type": question.question_type,
                    "correctness_percentage": question.correctness_percentage,
                    "distractors_chosen": [
                        {"text": choice.text, "percentage": choice.percentage}
                        for choice in question.choice_breakdown
                        if not choice.is_correct and choice.count > 0
                    ],
                    "anonymous_answers": [
                        {"answer": answer["answer"], "count": answer["count"]}
                        for answer in question.common_answers
                    ],
                }
                for question in insights.questions
            ],
            "high_confidence_incorrect_count": len(insights.high_confidence_incorrect),
            "low_confidence_correct_count": len(insights.low_confidence_correct),
        }


class RuleBasedInsightProvider(BaseInsightProvider):
    """Default provider: transparent rules over the deterministic figures.

    Every suggestion it makes can be traced to a threshold in settings, which
    means a teacher can predict its behaviour and it works offline.
    """

    name = "CariCue rules"

    def generate(self, insights: SessionInsights) -> list[Suggestion]:
        suggestions: list[Suggestion] = []
        low_threshold = settings.CARICUE["LOW_CORRECTNESS_THRESHOLD"]

        if insights.submitted_count == 0:
            return [
                Suggestion(
                    title="No submissions yet",
                    body=(
                        "Once students submit, CariCue will suggest what to "
                        "review based on the responses."
                    ),
                    category="summary",
                    source=self.name,
                )
            ]

        weak = [
            question
            for question in insights.questions
            if question.correctness_percentage is not None
            and question.response_count > 0
            and question.correctness_percentage < low_threshold
        ]
        for question in sorted(weak, key=lambda q: q.correctness_percentage)[:2]:
            body = (
                f"Only {question.correctness_percentage:.0f}% answered question "
                f"{question.position} correctly. Consider reteaching this point "
                "before moving on."
            )
            top_distractor = max(
                (c for c in question.choice_breakdown if not c.is_correct),
                key=lambda c: c.count,
                default=None,
            )
            if top_distractor is not None and top_distractor.count > 0:
                body += (
                    f' The most common wrong choice was "{top_distractor.text}" '
                    f"({top_distractor.percentage:.0f}%), which points at a "
                    "specific misconception rather than a random guess."
                )
            suggestions.append(
                Suggestion(
                    title=f"Reteach question {question.position}",
                    body=body,
                    category="misconception",
                    source=self.name,
                )
            )

        if insights.high_confidence_incorrect:
            count = len(insights.high_confidence_incorrect)
            suggestions.append(
                Suggestion(
                    title="Confident misconceptions to address",
                    body=(
                        f"{count} response(s) were incorrect but marked high "
                        "confidence. These students are unlikely to ask for "
                        "help, so a short whole-class correction may be more "
                        "effective than waiting for questions."
                    ),
                    category="misconception",
                    source=self.name,
                )
            )

        if insights.low_confidence_correct:
            count = len(insights.low_confidence_correct)
            suggestions.append(
                Suggestion(
                    title="Correct but unsure",
                    body=(
                        f"{count} response(s) were correct with low confidence. "
                        "A quick worked example could turn a guess into secure "
                        "understanding."
                    ),
                    category="follow_up",
                    source=self.name,
                )
            )

        if (
            insights.overall_correctness_percentage is not None
            and insights.overall_correctness_percentage >= 85
            and not weak
        ):
            suggestions.append(
                Suggestion(
                    title="Class looks ready to move on",
                    body=(
                        f"Auto-scored performance is "
                        f"{insights.overall_correctness_percentage:.0f}%. "
                        "Consider extending the topic rather than reviewing it."
                    ),
                    category="follow_up",
                    source=self.name,
                )
            )

        topic = insights.activity_topic or insights.activity_title
        if weak:
            focus = weak[0]
            suggestions.append(
                Suggestion(
                    title="Question for the next lesson",
                    body=(
                        f"Open the next class by asking students to explain, in "
                        f'their own words, the idea behind "{focus.prompt}". '
                        "Explanations surface reasoning that a multiple-choice "
                        "item cannot."
                    ),
                    category="next_question",
                    source=self.name,
                )
            )
        else:
            suggestions.append(
                Suggestion(
                    title="Question for the next lesson",
                    body=(
                        f'Ask students to apply "{topic}" to an unfamiliar '
                        "example to check transfer rather than recall."
                    ),
                    category="next_question",
                    source=self.name,
                )
            )

        return suggestions


class LLMInsightProvider(BaseInsightProvider):
    """Optional LLM-backed provider.

    Ships with a deterministic mock client so the seam is exercised end to end
    without a network call or an API key. Point `client` at a real
    implementation of `summarize(payload) -> list[dict]` to use a live model;
    the payload it receives is already redacted.
    """

    name = "AI assistant (review before use)"
    requires_api_key = True

    def __init__(self, client: Any | None = None) -> None:
        self.client = client or MockLLMClient(model=settings.INSIGHT_LLM_MODEL)

    def is_available(self) -> bool:
        return bool(settings.INSIGHT_LLM_API_KEY)

    def generate(self, insights: SessionInsights) -> list[Suggestion]:
        if not self.is_available():
            return []
        payload = self.build_redacted_prompt_payload(insights)
        try:
            raw = self.client.summarize(payload)
        except Exception:
            logger.exception("Insight provider %s failed", self.name)
            return []

        suggestions: list[Suggestion] = []
        for item in raw or []:
            if not isinstance(item, dict) or not item.get("body"):
                continue
            suggestions.append(
                Suggestion(
                    title=str(item.get("title", "AI suggestion"))[:120],
                    body=str(item["body"])[:1200],
                    category=str(item.get("category", "summary")),
                    source=self.name,
                )
            )
        return suggestions


class MockLLMClient:
    """Offline stand-in for a real model.

    Produces plausible, clearly-labelled text from the redacted payload so the
    provider contract and the UI's "suggestion" treatment can be tested.
    """

    def __init__(self, model: str = "mock-llm-v1") -> None:
        self.model = model

    def summarize(self, payload: dict[str, Any]) -> list[dict[str, str]]:
        topic = payload.get("topic") or "this topic"
        weakest = min(
            (
                question
                for question in payload.get("questions", [])
                if question.get("correctness_percentage") is not None
            ),
            key=lambda question: question["correctness_percentage"],
            default=None,
        )
        answers = [
            answer["answer"]
            for question in payload.get("questions", [])
            for answer in question.get("anonymous_answers", [])
        ]

        items: list[dict[str, str]] = []
        if answers:
            preview = ", ".join(f'"{answer}"' for answer in answers[:3])
            items.append(
                {
                    "title": "Open-text themes",
                    "body": (
                        f"Recurring wording in the written answers: {preview}. "
                        f"Read the full list before acting on this summary."
                    ),
                    "category": "summary",
                }
            )
        if weakest is not None:
            items.append(
                {
                    "title": "Possible misconception",
                    "body": (
                        f'Responses to "{weakest["prompt"]}" suggest students '
                        f"may be conflating related ideas within {topic}. "
                        "Verify against the response detail below."
                    ),
                    "category": "misconception",
                }
            )
        items.append(
            {
                "title": "Suggested follow-up activity",
                "body": (
                    f"A five-minute paired sorting task on {topic}, where "
                    "students justify each placement aloud, would surface the "
                    "reasoning behind these answers."
                ),
                "category": "follow_up",
            }
        )
        return items


def get_insight_provider() -> BaseInsightProvider:
    """Resolves the configured provider, falling back to the rule-based one."""
    path = settings.INSIGHT_PROVIDER
    try:
        provider_class = import_string(path)
        provider = provider_class()
    except Exception:
        logger.exception("Could not load insight provider %r; using rules.", path)
        return RuleBasedInsightProvider()

    if not isinstance(provider, BaseInsightProvider):
        logger.error("%r is not a BaseInsightProvider; using rules.", path)
        return RuleBasedInsightProvider()

    if not provider.is_available():
        logger.info("Provider %s unavailable (no API key); using rules.", provider.name)
        return RuleBasedInsightProvider()
    return provider


def generate_suggestions(insights: SessionInsights) -> list[dict]:
    provider = get_insight_provider()
    try:
        suggestions = provider.generate(insights)
    except Exception:
        logger.exception("Provider %s raised; returning no suggestions.", provider.name)
        return []
    return [suggestion.as_dict() for suggestion in suggestions]
