"""Live sessions, participants, responses and the teacher's reflection.

Naming note: the model is `LiveSession`, not `Session`, so it never collides
with `django.contrib.sessions.models.Session` in imports, admin or queries.

Two identifiers exist per session and they have different jobs:

``code``
    Six characters a teacher can read aloud. Short, therefore guessable,
    therefore the lookup endpoint that accepts it is rate-limited and only
    ever returns the public token for an *open* session.
``public_token``
    32 hex characters from `secrets`. This is what QR codes encode and what
    every public read/write endpoint requires.
"""

from __future__ import annotations

import secrets

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone

from caricue.activities.models import (
    CONFIDENCE_MAX,
    CONFIDENCE_MIN,
    Activity,
    Choice,
    Question,
)
from caricue.classroom.models import Classroom, Student
from caricue.core.models import TimeStampedModel

# Excludes 0/O/1/I/L to keep codes unambiguous when read aloud or written down.
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


class SessionStatus(models.TextChoices):
    OPEN = "open", "Open"
    CLOSED = "closed", "Closed"


class IdentityMode(models.TextChoices):
    DISPLAY_NAME = "display_name", "Student types a display name"
    ROSTER_IDENTIFIER = "roster_identifier", "Student enters their roster identifier"
    GOOGLE_ACCOUNT = "google_account", "Student signs in with school Google account"


class PlanImpact(models.TextChoices):
    CONFIRMED = "confirmed", "Confirmed my lesson plan"
    CHANGED = "changed", "Changed my lesson plan"
    UNCLEAR = "unclear", "Still unclear / need more evidence"


def generate_short_code(length: int | None = None) -> str:
    size = length or settings.CARICUE["SHORT_CODE_LENGTH"]
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(size))


def generate_public_token() -> str:
    return secrets.token_hex(16)


class LiveSession(TimeStampedModel):
    activity = models.ForeignKey(
        Activity,
        on_delete=models.CASCADE,
        related_name="live_sessions",
    )
    classroom = models.ForeignKey(
        Classroom,
        on_delete=models.CASCADE,
        related_name="live_sessions",
    )
    code = models.CharField(max_length=12, unique=True, db_index=True)
    public_token = models.CharField(max_length=64, unique=True, db_index=True)
    status = models.CharField(
        max_length=10,
        choices=SessionStatus.choices,
        default=SessionStatus.OPEN,
        db_index=True,
    )
    identity_mode = models.CharField(
        max_length=20,
        choices=IdentityMode.choices,
        default=IdentityMode.DISPLAY_NAME,
    )
    started_at = models.DateTimeField(default=timezone.now)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]
        constraints = [
            # A closed session must record when it closed, and an open one
            # must not; keeps every downstream duration calculation honest.
            models.CheckConstraint(
                condition=(
                    models.Q(status=SessionStatus.CLOSED, closed_at__isnull=False)
                    | models.Q(status=SessionStatus.OPEN, closed_at__isnull=True)
                ),
                name="live_session_closed_at_matches_status",
            ),
        ]
        indexes = [models.Index(fields=["classroom", "status"])]

    def __str__(self) -> str:
        return f"{self.activity.title} ({self.code})"

    @property
    def owner_teacher_id(self) -> int | None:
        return self.activity.teacher_id

    @property
    def is_open(self) -> bool:
        return self.status == SessionStatus.OPEN

    @property
    def join_url(self) -> str:
        """The URL a QR code encodes."""
        return f"{settings.PUBLIC_BASE_URL}/s/{self.public_token}"

    @property
    def roster_size(self) -> int:
        return self.classroom.enrollments.filter(is_active=True).count()

    def close(self) -> None:
        if not self.is_open:
            return
        self.status = SessionStatus.CLOSED
        self.closed_at = timezone.now()
        self.save(update_fields=["status", "closed_at", "updated_at"])


class Participant(TimeStampedModel):
    """One student's attempt at one session.

    No account, no password. The client is handed an opaque `participant_token`
    on join and presents it to submit; that token is the only thing that lets
    a submission be attributed, and it is never derivable from the roster.
    """

    live_session = models.ForeignKey(
        LiveSession,
        on_delete=models.CASCADE,
        related_name="participants",
    )
    student = models.ForeignKey(
        Student,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="participations",
        help_text="Set when the session identifies students against the roster.",
    )
    display_name = models.CharField(
        max_length=80,
        blank=True,
        help_text="Self-entered label, or the roster identifier that was used.",
    )
    submitted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    participant_token = models.CharField(
        max_length=64,
        unique=True,
        default=generate_public_token,
        editable=False,
    )

    class Meta:
        ordering = ["created_at"]
        constraints = [
            # A roster-identified student joins a given session once.
            models.UniqueConstraint(
                fields=["live_session", "student"],
                condition=models.Q(student__isnull=False),
                name="uniq_participant_student_per_session",
            ),
            # Self-entered names are also unique per session, so a second
            # device using the same name cannot silently overwrite the first.
            models.UniqueConstraint(
                "live_session",
                Lower("display_name"),
                condition=models.Q(student__isnull=True) & ~models.Q(display_name=""),
                name="uniq_participant_display_name_per_session",
            ),
        ]

    def __str__(self) -> str:
        return self.label

    @property
    def owner_teacher_id(self) -> int | None:
        return self.live_session.activity.teacher_id

    @property
    def label(self) -> str:
        """What the teacher sees. Falls back to an opaque local id."""
        if self.student_id and self.student is not None:
            return self.student.display_name
        return self.display_name or f"Participant {self.pk}"

    @property
    def has_submitted(self) -> bool:
        return self.submitted_at is not None


class Response(TimeStampedModel):
    """One participant's answer to one question."""

    participant = models.ForeignKey(
        Participant,
        on_delete=models.CASCADE,
        related_name="responses",
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="responses",
    )
    selected_choice = models.ForeignKey(
        Choice,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="responses",
    )
    text_response = models.TextField(max_length=1000, blank=True)
    confidence_value = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[
            MinValueValidator(CONFIDENCE_MIN),
            MaxValueValidator(CONFIDENCE_MAX),
        ],
    )
    is_correct = models.BooleanField(
        null=True,
        blank=True,
        help_text="Null when the question is not deterministically scorable.",
    )

    class Meta:
        ordering = ["question__position", "id"]
        constraints = [
            # The database-level guarantee behind "submit once".
            models.UniqueConstraint(
                fields=["participant", "question"],
                name="uniq_response_per_participant_question",
            ),
            models.CheckConstraint(
                condition=models.Q(confidence_value__isnull=True)
                | models.Q(
                    confidence_value__gte=CONFIDENCE_MIN,
                    confidence_value__lte=CONFIDENCE_MAX,
                ),
                name="response_confidence_within_scale",
            ),
        ]
        indexes = [models.Index(fields=["question", "is_correct"])]

    def __str__(self) -> str:
        return f"{self.participant.label} -> Q{self.question.position}"

    @property
    def owner_teacher_id(self) -> int | None:
        return self.participant.live_session.activity.teacher_id


class TeacherReflection(TimeStampedModel):
    """The instructional decision a session led to.

    This is the point of the product: evidence is only useful if it changes
    what happens in the next lesson, so the reflection is a first-class record
    rather than a free-text note bolted onto the session.
    """

    live_session = models.OneToOneField(
        LiveSession,
        on_delete=models.CASCADE,
        related_name="reflection",
    )
    primary_gap = models.CharField(
        max_length=250,
        help_text="The main learning gap this check surfaced.",
    )
    plan_impact = models.CharField(
        max_length=16,
        choices=PlanImpact.choices,
        default=PlanImpact.CONFIRMED,
    )
    planned_action = models.TextField(
        max_length=1000,
        help_text="What the teacher will review, reteach or reinforce.",
    )
    notes = models.TextField(max_length=2000, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Reflection on {self.live_session.code}"

    @property
    def owner_teacher_id(self) -> int | None:
        return self.live_session.activity.teacher_id


def allocate_unique_code(max_attempts: int = 12) -> str:
    """Draws a short code that is not already used by an existing session."""
    for _ in range(max_attempts):
        candidate = generate_short_code()
        if not LiveSession.objects.filter(code=candidate).exists():
            return candidate
    # Extremely unlikely; widen the code rather than fail the launch.
    for extra in range(1, 5):
        candidate = generate_short_code(settings.CARICUE["SHORT_CODE_LENGTH"] + extra)
        if not LiveSession.objects.filter(code=candidate).exists():
            return candidate
        raise RuntimeError("Could not allocate a unique session code.")
