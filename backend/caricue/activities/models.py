"""Formative activities: a short set of questions a teacher can launch."""

from __future__ import annotations

import os
import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from caricue.classroom.models import Classroom
from caricue.core.models import TimeStampedModel


class ActivityStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    PUBLISHED = "published", "Published"


class ActivityKind(models.TextChoices):
    QUIZ = "quiz", "Quiz (marked)"
    SURVEY = "survey", "Survey (unmarked)"


class QuestionType(models.TextChoices):
    MULTIPLE_CHOICE = "multiple_choice", "Multiple choice"
    SHORT_TEXT = "short_text", "Short text"
    CONFIDENCE = "confidence", "Confidence scale (1-5)"
    MULTI_SELECT = "multi_select", "Multi-select (tick all that apply)"
    RATING = "rating", "Rating scale (1-5)"


#: Question types CariCue can score without a human or an LLM.
AUTO_SCORED_TYPES = frozenset({QuestionType.MULTIPLE_CHOICE, QuestionType.SHORT_TEXT})

#: Types that only make sense when nothing is marked right or wrong.
SURVEY_ONLY_TYPES = frozenset({QuestionType.MULTI_SELECT, QuestionType.RATING})

#: Types whose answer is picked from the question's `choices`.
CHOICE_TYPES = frozenset({QuestionType.MULTIPLE_CHOICE, QuestionType.MULTI_SELECT})

CONFIDENCE_MIN = 1
CONFIDENCE_MAX = 5

RATING_MIN = 1
RATING_MAX = 5


class Activity(TimeStampedModel):
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="activities",
    )
    classroom = models.ForeignKey(
        Classroom,
        on_delete=models.CASCADE,
        related_name="activities",
    )
    title = models.CharField(max_length=150)
    topic = models.CharField(
        max_length=250,
        blank=True,
        help_text="Topic or learning objective this check targets.",
    )
    status = models.CharField(
        max_length=16,
        choices=ActivityStatus.choices,
        default=ActivityStatus.DRAFT,
    )
    kind = models.CharField(
        max_length=10,
        choices=ActivityKind.choices,
        default=ActivityKind.QUIZ,
        help_text=(
            "Quizzes are marked and feed the insights. Surveys collect "
            "opinions and are never scored."
        ),
    )
    follow_up_of_session = models.ForeignKey(
        "live.LiveSession",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="follow_up_activities",
        help_text="Set when this draft was generated from a prior live session.",
    )
    review_item = models.ForeignKey(
        "reviews.ReviewItem",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activities",
        help_text="Set when this draft was generated from a spaced-review card.",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "activities"

    def __str__(self) -> str:
        return self.title

    @property
    def question_count(self) -> int:
        return self.questions.count()

    @property
    def is_survey(self) -> bool:
        return self.kind == ActivityKind.SURVEY

    def is_launchable(self) -> tuple[bool, str]:
        """Whether this activity can start a live session, and why not."""
        limits = settings.CARICUE
        questions = list(self.questions.prefetch_related("choices"))
        if len(questions) < limits["MIN_QUESTIONS_PER_ACTIVITY"]:
            return False, "Add at least one question before launching."
        if len(questions) > limits["MAX_QUESTIONS_PER_ACTIVITY"]:
            return (
                False,
                f"An activity may have at most "
                f"{limits['MAX_QUESTIONS_PER_ACTIVITY']} questions.",
            )
        for question in questions:
            if not self.is_survey and question.question_type in SURVEY_ONLY_TYPES:
                return (
                    False,
                    f"Question {question.position} is a survey question type.",
                )
            if question.question_type in CHOICE_TYPES:
                choices = list(question.choices.all())
                if len(choices) < 2:
                    return (
                        False,
                        f"Question {question.position} needs at least two choices.",
                    )
                if (
                    not self.is_survey
                    and question.question_type == QuestionType.MULTIPLE_CHOICE
                    and not any(choice.is_correct for choice in choices)
                ):
                    return (
                        False,
                        f"Question {question.position} needs a correct choice marked.",
                    )
        return True, ""


def question_image_upload_path(instance: QuestionImage, filename: str) -> str:
    """Random, unguessable name; the original filename is never kept.

    The extension is whatever the re-encoded bytes need (`.jpg`, `.png`,
    `.webp`), decided by `activities.images.process_upload`.
    """
    extension = os.path.splitext(filename)[1].lower() or ".jpg"
    return f"question-images/{uuid.uuid4().hex}{extension}"


class QuestionImage(TimeStampedModel):
    """An uploaded picture a teacher can attach to a question.

    Uploaded on its own (before the question is saved) so the builder can show
    a preview immediately. Unattached rows are swept by `prune_orphan_images`.
    """

    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="question_images",
    )
    file = models.ImageField(
        upload_to=question_image_upload_path,
        width_field="width",
        height_field="height",
    )
    width = models.PositiveIntegerField(default=0)
    height = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Image {self.pk}"

    @property
    def owner_teacher_id(self) -> int | None:
        return self.teacher_id

    @property
    def url(self) -> str:
        return self.file.url if self.file else ""


class Question(TimeStampedModel):
    activity = models.ForeignKey(
        Activity,
        on_delete=models.CASCADE,
        related_name="questions",
    )
    image = models.ForeignKey(
        QuestionImage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="questions",
        help_text="Optional picture shown with the prompt.",
    )
    image_alt = models.CharField(
        max_length=250,
        blank=True,
        help_text="Describes the picture for students who cannot see it.",
    )
    position = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1)],
        help_text="1-based display order.",
    )
    prompt = models.TextField(max_length=500)
    question_type = models.CharField(max_length=20, choices=QuestionType.choices)
    is_required = models.BooleanField(default=True)
    collect_confidence = models.BooleanField(
        default=False,
        help_text=(
            "Ask the student how confident they are (1-5) alongside this "
            "question. Enables performance-versus-confidence signals."
        ),
    )
    rating_low_label = models.CharField(
        max_length=60,
        blank=True,
        help_text="Caption for 1 on a rating question, e.g. 'Not at all'.",
    )
    rating_high_label = models.CharField(
        max_length=60,
        blank=True,
        help_text="Caption for 5 on a rating question, e.g. 'Completely'.",
    )
    accepted_answers = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            "Short-text answers accepted as correct. Compared after trimming "
            "whitespace and lowercasing. Empty means the question is not "
            "auto-scored."
        ),
    )
    source_question = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="follow_up_questions",
        help_text="Weak question this follow-up item targets.",
    )
    source_session = models.ForeignKey(
        "live.LiveSession",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="follow_up_questions",
        help_text="Session that motivated this follow-up question.",
    )

    class Meta:
        ordering = ["position", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["activity", "position"],
                name="uniq_question_position_per_activity",
            ),
        ]

    def __str__(self) -> str:
        return f"Q{self.position}: {self.prompt[:40]}"

    @property
    def owner_teacher_id(self) -> int | None:
        return self.activity.teacher_id

    @property
    def image_url(self) -> str | None:
        """Same-origin path (`/media/...`) so it survives any proxy or host."""
        return self.image.url if self.image_id and self.image.file else None

    @property
    def is_auto_scored(self) -> bool:
        """True when correctness can be determined deterministically."""
        if self.activity.kind == ActivityKind.SURVEY:
            return False  # surveys are never marked
        if self.question_type == QuestionType.MULTIPLE_CHOICE:
            return True
        if self.question_type == QuestionType.SHORT_TEXT:
            return bool(self.normalized_accepted_answers())
        return False

    def normalized_accepted_answers(self) -> list[str]:
        """Accepted answers after the only transformations we apply."""
        if not isinstance(self.accepted_answers, list):
            return []
        return [
            normalize_text_answer(answer)
            for answer in self.accepted_answers
            if isinstance(answer, str) and normalize_text_answer(answer)
        ]


class Choice(TimeStampedModel):
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="choices",
    )
    text = models.CharField(max_length=250)
    is_correct = models.BooleanField(default=False)
    position = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(50)],
    )

    class Meta:
        ordering = ["position", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["question", "position"],
                name="uniq_choice_position_per_question",
            ),
        ]

    def __str__(self) -> str:
        return self.text

    @property
    def owner_teacher_id(self) -> int | None:
        return self.question.activity.teacher_id


def normalize_text_answer(value: str | None) -> str:
    """The complete, intentionally transparent short-text normalisation.

    Trim surrounding whitespace, collapse internal runs of whitespace, and
    lowercase. Nothing else: no stemming, no fuzzy matching, no LLM. Teachers
    can predict exactly what will be marked correct.
    """
    if not value:
        return ""
    return " ".join(str(value).split()).lower()
