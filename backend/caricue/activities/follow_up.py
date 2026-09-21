"""Generate draft follow-up activities from session misconception cards."""

from __future__ import annotations

from django.conf import settings
from django.db import transaction

from caricue.accounts.models import Teacher
from caricue.activities.models import (
    Activity,
    ActivityStatus,
    Choice,
    Question,
    QuestionType,
)
from caricue.insights.misconceptions import build_misconception_cards
from caricue.insights.service import build_session_insights
from caricue.live.models import LiveSession


@transaction.atomic
def create_follow_up_activity(
    session: LiveSession,
    teacher: Teacher,
    *,
    question_ids: list[int] | None = None,
    include_confidence: bool = True,
) -> Activity:
    """Create a draft activity targeting weak areas from a session."""
    if session.activity.teacher_id != teacher.pk:
        raise PermissionError("Session not owned by teacher.")

    insights = build_session_insights(session)
    cards = build_misconception_cards(insights)

    if question_ids:
        id_set = set(question_ids)
        cards = [card for card in cards if card.question_id in id_set]
    else:
        cards = cards[:2]

    if not cards:
        raise ValueError("No misconception cards available for follow-up.")

    activity = session.activity
    follow_up = Activity.objects.create(
        teacher=teacher,
        classroom=session.classroom,
        title=f"Follow-up: {activity.title}",
        topic=activity.topic,
        status=ActivityStatus.DRAFT,
        follow_up_of_session=session,
    )

    max_questions = settings.CARICUE["MAX_QUESTIONS_PER_ACTIVITY"]
    position = 1
    source_questions = {
        q.pk: q for q in activity.questions.prefetch_related("choices").all()
    }

    for card in cards:
        if position > max_questions:
            break
        source = source_questions.get(card.question_id)
        if source is None:
            continue

        if source.question_type == QuestionType.MULTIPLE_CHOICE:
            _create_mcq_follow_up(
                follow_up, source, session, position, card.question_id
            )
            position += 1
        elif source.question_type == QuestionType.SHORT_TEXT:
            _create_short_text_follow_up(
                follow_up, source, session, position, card.question_id
            )
            position += 1

    if (
        include_confidence
        and position <= max_questions
        and insights.has_confidence_data
    ):
        topic_label = activity.topic or activity.title
        Question.objects.create(
            activity=follow_up,
            position=position,
            prompt=f"How sure are you about {topic_label} now?",
            question_type=QuestionType.CONFIDENCE,
            source_session=session,
        )

    return follow_up


def _create_mcq_follow_up(
    follow_up: Activity,
    source: Question,
    session: LiveSession,
    position: int,
    source_question_id: int,
) -> Question:
    correct = source.choices.filter(is_correct=True).first()
    top_wrong = (
        source.choices.filter(is_correct=False).order_by("position").first()
    )
    question = Question.objects.create(
        activity=follow_up,
        position=position,
        prompt=source.prompt,
        question_type=QuestionType.MULTIPLE_CHOICE,
        collect_confidence=True,
        source_question_id=source_question_id,
        source_session=session,
    )
    choices = []
    if correct:
        choices.append((correct.text, True, 1))
    if top_wrong:
        choices.append((top_wrong.text, False, 2))
    for other in source.choices.filter(is_correct=False).exclude(
        pk=top_wrong.pk if top_wrong else None
    )[:2]:
        choices.append((other.text, False, len(choices) + 1))
    if not choices and correct:
        choices = [(correct.text, True, 1)]
    for text, is_correct, pos in choices:
        Choice.objects.create(
            question=question, text=text, is_correct=is_correct, position=pos
        )
    return question


def _create_short_text_follow_up(
    follow_up: Activity,
    source: Question,
    session: LiveSession,
    position: int,
    source_question_id: int,
) -> Question:
    return Question.objects.create(
        activity=follow_up,
        position=position,
        prompt=f"Explain in your own words: {source.prompt}",
        question_type=QuestionType.SHORT_TEXT,
        collect_confidence=True,
        accepted_answers=list(source.accepted_answers or []),
        source_question_id=source_question_id,
        source_session=session,
    )
