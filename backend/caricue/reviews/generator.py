"""Draft a review activity from a class's question history on one topic."""

from __future__ import annotations

from django.conf import settings
from django.db import transaction

from caricue.accounts.models import Teacher
from caricue.activities.follow_up import (
    _create_mcq_follow_up,
    _create_short_text_follow_up,
)
from caricue.activities.models import Activity, ActivityStatus, Question, QuestionType
from caricue.insights.service import build_session_insights
from caricue.insights.topics import topic_for_session
from caricue.live.models import LiveSession, SessionStatus

from .models import ReviewItem


def _root_question_id(question: Question) -> int:
    seen: set[int] = set()
    current = question
    while current.source_question_id and current.source_question_id not in seen:
        seen.add(current.pk)
        parent = current.source_question
        if parent is None:
            break
        current = parent
    return current.pk


@transaction.atomic
def create_review_activity(item: ReviewItem, teacher: Teacher) -> Activity:
    """Builds a draft quiz from the weakest (and a couple of mastered) items.

    Never launched automatically: the teacher reviews the draft first.
    """
    if item.classroom.teacher_id != teacher.pk:
        raise PermissionError("Review item not owned by teacher.")

    sessions = list(
        LiveSession.objects.filter(
            classroom=item.classroom,
            status=SessionStatus.CLOSED,
        )
        .exclude(activity__kind="survey")
        .select_related("activity")
        .prefetch_related("activity__questions__choices")
        .order_by("-closed_at")
    )
    history: dict[int, tuple[float, Question, LiveSession]] = {}
    for session in sessions:
        if topic_for_session(session) != item.topic_key:
            continue
        insights = build_session_insights(session)
        by_id = {qi.question_id: qi for qi in insights.questions}
        for question in session.activity.questions.all():
            if question.question_type not in {
                QuestionType.MULTIPLE_CHOICE,
                QuestionType.SHORT_TEXT,
            }:
                continue
            insight = by_id.get(question.pk)
            score = (
                insight.correctness_percentage
                if insight and insight.correctness_percentage is not None
                else 100.0
            )
            root = _root_question_id(question)
            previous = history.get(root)
            if previous is None or session.closed_at >= previous[2].closed_at:
                history[root] = (score, question, session)

    if not history:
        raise ValueError("No scored questions on this topic to review.")

    ranked = sorted(history.values(), key=lambda row: (row[0], row[1].position))
    weak = [row for row in ranked if row[0] < 80]
    mastered = [row for row in ranked if row[0] >= 80]
    cap = settings.CARICUE["REVIEW_ACTIVITY_MAX_QUESTIONS"]
    picked = weak[: max(cap - 2, 1)]
    remaining = cap - len(picked)
    if remaining > 0:
        picked.extend(mastered[:remaining])
    if not picked:
        picked = ranked[:cap]

    activity = Activity.objects.create(
        teacher=teacher,
        classroom=item.classroom,
        title=f"Review: {item.topic_label}",
        topic=item.topic_label,
        status=ActivityStatus.DRAFT,
        review_item=item,
        follow_up_of_session=item.last_session,
    )

    position = 1
    for _score, source, session in picked:
        if source.question_type == QuestionType.MULTIPLE_CHOICE:
            _create_mcq_follow_up(activity, source, session, position, source.pk)
        else:
            _create_short_text_follow_up(activity, source, session, position, source.pk)
        position += 1

    if activity.questions.count() == 0:
        activity.delete()
        raise ValueError("No scored questions on this topic to review.")

    return activity
