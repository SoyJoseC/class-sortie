"""Deterministic Leitner updates for class-level review cards."""

from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from caricue.insights.service import build_session_insights
from caricue.insights.topics import topic_for_session
from caricue.live.models import LiveSession

from .models import ReviewEvent, ReviewItem

PROMOTE_SCORE = 80.0
RESET_SCORE = 60.0


def review_intervals() -> list[int]:
    raw = settings.CARICUE["REVIEW_INTERVALS_DAYS"]
    return [max(1, int(days)) for days in raw] or [1, 3, 7, 14, 30, 60]


def next_box(
    current: int, score: float, *, high_confidence_wrong: bool
) -> tuple[int, str]:
    """(new_box, reason) for one scored quiz."""
    if score < RESET_SCORE or high_confidence_wrong:
        return 0, ReviewEvent.Reason.RESET
    if score >= PROMOTE_SCORE:
        to_box = min(5, current + 1)
        reason = (
            ReviewEvent.Reason.PROMOTED if to_box > current else ReviewEvent.Reason.HELD
        )
        return to_box, reason
    return current, ReviewEvent.Reason.HELD


def interval_for_box(box: int) -> int:
    intervals = review_intervals()
    index = min(max(box, 0), len(intervals) - 1)
    return intervals[index]


def due_queryset(queryset=None, *, when=None):
    """Items whose next check is due and not snoozed past `when`."""
    moment = when or timezone.now()
    qs = queryset if queryset is not None else ReviewItem.objects.all()
    return qs.filter(due_at__lte=moment).exclude(snoozed_until__gt=moment)


@transaction.atomic
def apply_session_to_schedule(session: LiveSession) -> ReviewItem | None:
    """Moves the class's card for this session's topic, or creates one.

    Surveys and sessions with no auto-scored answers are ignored: there is
    nothing honest to schedule from them.
    """
    if session.activity.is_survey:
        return None

    insights = build_session_insights(session)
    score = insights.overall_correctness_percentage
    if not insights.has_auto_scored_data or score is None:
        return None

    topic_key = topic_for_session(session)
    if not topic_key:
        return None

    topic_label = session.activity.topic or session.activity.title
    item, created = ReviewItem.objects.select_for_update().get_or_create(
        classroom=session.classroom,
        topic_key=topic_key,
        defaults={
            "topic_label": topic_label,
            "box": 0,
            "due_at": timezone.now(),
        },
    )

    from_box = 0 if created else item.box
    to_box, reason = next_box(
        from_box,
        score,
        high_confidence_wrong=bool(insights.high_confidence_incorrect),
    )

    now = timezone.now()
    item.topic_label = topic_label
    item.box = to_box
    item.last_score = score
    item.last_session = session
    item.due_at = now + timedelta(days=interval_for_box(to_box))
    item.snoozed_until = None
    item.save()

    ReviewEvent.objects.create(
        review_item=item,
        session=session,
        from_box=from_box,
        to_box=to_box,
        score=score,
        reason=ReviewEvent.Reason.CREATED if created else reason,
    )
    return item


@transaction.atomic
def snooze_review_item(item: ReviewItem, *, days: int = 1) -> ReviewItem:
    """Pushes the next check back without changing the box."""
    days = max(1, min(days, 60))
    until = timezone.now() + timedelta(days=days)
    item.snoozed_until = until
    item.save(update_fields=["snoozed_until", "updated_at"])
    ReviewEvent.objects.create(
        review_item=item,
        from_box=item.box,
        to_box=item.box,
        score=item.last_score,
        reason=ReviewEvent.Reason.SNOOZED,
    )
    return item


def rebuild_schedule(*, teacher=None) -> int:
    """Replays closed quiz sessions in order so the cards match history."""
    sessions = (
        LiveSession.objects.filter(status="closed")
        .exclude(activity__kind="survey")
        .select_related("activity", "classroom")
        .order_by("closed_at", "pk")
    )
    if teacher is not None:
        sessions = sessions.filter(activity__teacher=teacher)

    ReviewItem.objects.filter(
        **({"classroom__teacher": teacher} if teacher is not None else {})
    ).delete()

    updated = 0
    for session in sessions:
        if apply_session_to_schedule(session) is not None:
            updated += 1
    return updated
