"""Class-level spaced review: Leitner boxes, due dates, draft generation."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from caricue.activities.models import Activity, ActivityKind, Question, QuestionType
from caricue.live.services import (
    close_session,
    join_session,
    launch_session,
    submit_responses,
)
from caricue.reviews.generator import create_review_activity
from caricue.reviews.models import ReviewEvent, ReviewItem

pytestmark = pytest.mark.django_db


def _submit_scored(open_session, answers_for, *, correct: bool, confidence: int = 3):
    result = join_session(
        session=open_session, identifier=f"Student {correct} {confidence}"
    )
    submit_responses(
        session=open_session,
        participant=result.participant,
        answers=answers_for(
            open_session.activity, correct=correct, confidence=confidence
        ),
    )


def test_closing_a_strong_quiz_promotes_the_card(open_session, answers_for, activity):
    _submit_scored(open_session, answers_for, correct=True, confidence=4)
    close_session(open_session)

    item = ReviewItem.objects.get(classroom=activity.classroom)
    assert item.box == 1
    assert item.last_score >= 80
    assert item.due_at > timezone.now()
    assert ReviewEvent.objects.filter(reason=ReviewEvent.Reason.CREATED).exists()


def test_a_weak_or_overconfident_quiz_resets_the_box(
    open_session, answers_for, activity, settings
):
    settings.CARICUE = {
        **settings.CARICUE,
        "HIGH_CONFIDENCE_THRESHOLD": 4,
    }
    _submit_scored(open_session, answers_for, correct=False, confidence=5)
    close_session(open_session)

    item = ReviewItem.objects.get(classroom=activity.classroom)
    assert item.box == 0
    assert item.last_score is not None and item.last_score < 60


def test_box_rules_are_plain_percentages():
    from caricue.reviews.schedule import next_box

    assert next_box(2, 85, high_confidence_wrong=False) == (
        3,
        ReviewEvent.Reason.PROMOTED,
    )
    assert next_box(5, 90, high_confidence_wrong=False) == (5, ReviewEvent.Reason.HELD)
    assert next_box(3, 70, high_confidence_wrong=False) == (3, ReviewEvent.Reason.HELD)
    assert next_box(3, 50, high_confidence_wrong=False) == (0, ReviewEvent.Reason.RESET)
    assert next_box(4, 90, high_confidence_wrong=True) == (0, ReviewEvent.Reason.RESET)


def test_surveys_do_not_create_review_cards(teacher, classroom):
    from caricue.activities.models import Choice

    survey = Activity.objects.create(
        teacher=teacher, classroom=classroom, title="Feedback", kind=ActivityKind.SURVEY
    )
    q = Question.objects.create(
        activity=survey,
        position=1,
        prompt="Useful?",
        question_type=QuestionType.MULTI_SELECT,
    )
    Choice.objects.create(question=q, text="Yes", position=1)
    Choice.objects.create(question=q, text="No", position=2)
    session, error = launch_session(activity=survey, identity_mode="anonymous")
    assert error == ""
    close_session(session)

    assert not ReviewItem.objects.exists()


def test_due_list_and_snooze_and_isolation(
    auth_client, other_client, open_session, answers_for, activity
):
    _submit_scored(open_session, answers_for, correct=True)
    close_session(open_session)
    item = ReviewItem.objects.get()
    item.due_at = timezone.now() - timedelta(hours=1)
    item.save(update_fields=["due_at"])

    due = auth_client.get(reverse("review-due"))
    assert due.status_code == 200
    assert due.data[0]["id"] == item.pk
    assert due.data[0]["is_due"] is True

    other = other_client.get(reverse("review-due"))
    assert other.data == []

    hidden = other_client.post(
        reverse("reviewitem-snooze", args=[item.pk]), {}, format="json"
    )
    assert hidden.status_code == 404

    snoozed = auth_client.post(
        reverse("reviewitem-snooze", args=[item.pk]), {"days": 2}, format="json"
    )
    assert snoozed.status_code == 200
    assert snoozed.data["is_due"] is False

    schedule = auth_client.get(
        reverse("classroom-review-schedule", args=[activity.classroom_id])
    )
    assert schedule.status_code == 200
    assert schedule.data[0]["topic_label"]


def test_create_review_activity_picks_weak_questions(
    auth_client, open_session, answers_for, activity, teacher
):
    _submit_scored(open_session, answers_for, correct=False, confidence=3)
    close_session(open_session)
    item = ReviewItem.objects.get()
    item.due_at = timezone.now() - timedelta(hours=1)
    item.save(update_fields=["due_at"])

    created = create_review_activity(item, teacher)
    assert created.review_item_id == item.pk
    assert created.status == "draft"
    assert created.questions.exists()

    response = auth_client.post(
        reverse("reviewitem-create-activity", args=[item.pk]), {}, format="json"
    )
    assert response.status_code == 201
    assert Activity.objects.filter(
        pk=response.data["activity_id"], review_item=item
    ).exists()


def test_overview_lists_due_reviews(auth_client, open_session, answers_for):
    _submit_scored(open_session, answers_for, correct=True)
    close_session(open_session)
    ReviewItem.objects.update(due_at=timezone.now() - timedelta(minutes=5))

    response = auth_client.get(reverse("teacher-overview"))

    assert response.status_code == 200
    assert response.data["due_reviews"]
    assert response.data["due_reviews"][0]["is_due"] is True


def test_rebuild_command_replays_history(open_session, answers_for, activity):
    from caricue.reviews.schedule import rebuild_schedule

    _submit_scored(open_session, answers_for, correct=True)
    # Bypass the live hook so we can prove the command rebuilds from scratch.
    open_session.close()
    ReviewItem.objects.all().delete()

    count = rebuild_schedule()

    assert count >= 1
    assert ReviewItem.objects.filter(classroom=activity.classroom).exists()
