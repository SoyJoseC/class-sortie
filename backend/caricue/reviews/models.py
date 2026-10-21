"""Class-level spaced review: one Leitner card per classroom and topic."""

from __future__ import annotations

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from caricue.core.models import TimeStampedModel


class ReviewItem(TimeStampedModel):
    """One topic the class should come back to.

    Students are usually anonymous, so the queue is per classroom and
    normalised topic, not per person. `box` is a Leitner box (0-5); `due_at`
    is when the next check is due.
    """

    classroom = models.ForeignKey(
        "classroom.Classroom",
        on_delete=models.CASCADE,
        related_name="review_items",
    )
    topic_key = models.CharField(max_length=250)
    topic_label = models.CharField(max_length=250)
    box = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)],
    )
    last_score = models.FloatField(null=True, blank=True)
    last_session = models.ForeignKey(
        "live.LiveSession",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="review_items",
    )
    due_at = models.DateTimeField()
    snoozed_until = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["due_at", "topic_label"]
        constraints = [
            models.UniqueConstraint(
                fields=["classroom", "topic_key"],
                name="reviewitem_unique_classroom_topic",
            ),
            models.CheckConstraint(
                condition=models.Q(box__gte=0) & models.Q(box__lte=5),
                name="reviewitem_box_0_to_5",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.topic_label} (box {self.box})"

    @property
    def owner_teacher_id(self) -> int:
        return self.classroom.teacher_id

    def is_due(self, when=None) -> bool:
        moment = when or timezone.now()
        if self.snoozed_until and self.snoozed_until > moment:
            return False
        return self.due_at <= moment


class ReviewEvent(models.Model):
    """Append-only history of a review card moving (or being snoozed)."""

    class Reason(models.TextChoices):
        CREATED = "created", "Created"
        PROMOTED = "promoted", "Promoted"
        HELD = "held", "Held"
        RESET = "reset", "Reset"
        SNOOZED = "snoozed", "Snoozed"

    review_item = models.ForeignKey(
        ReviewItem, on_delete=models.CASCADE, related_name="events"
    )
    session = models.ForeignKey(
        "live.LiveSession",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="review_events",
    )
    from_box = models.PositiveSmallIntegerField()
    to_box = models.PositiveSmallIntegerField()
    score = models.FloatField(null=True, blank=True)
    reason = models.CharField(max_length=16, choices=Reason.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.review_item_id}: {self.reason} {self.from_box}->{self.to_box}"
