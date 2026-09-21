from __future__ import annotations

from django.conf import settings
from django.db import transaction
from rest_framework import serializers

from caricue.classroom.models import Classroom

from .models import (
    Activity,
    ActivityStatus,
    Choice,
    Question,
    QuestionType,
    normalize_text_answer,
)


class ChoiceSerializer(serializers.ModelSerializer):
    """Nested inside `QuestionSerializer`, and usable standalone.

    `question` is only required for standalone writes.
    """

    id = serializers.IntegerField(required=False)
    question = serializers.PrimaryKeyRelatedField(
        queryset=Question.objects.all(), required=False
    )
    position = serializers.IntegerField(required=False, min_value=1)

    class Meta:
        model = Choice
        fields = ["id", "question", "text", "is_correct", "position"]
        # The `(question, position)` unique constraint would otherwise make
        # DRF demand both fields on every nested write, but the parent
        # serializer assigns them. Uniqueness is still enforced by `validate`
        # above and, ultimately, by the database constraint.
        validators = []

    def validate_text(self, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise serializers.ValidationError("Choice text is required.")
        return cleaned

    def validate_question(self, value: Question) -> Question:
        if value.activity.teacher_id != self.context["request"].user.pk:
            raise serializers.ValidationError("Question not found.")
        if value.question_type != QuestionType.MULTIPLE_CHOICE:
            raise serializers.ValidationError(
                "Only multiple-choice questions can have choices."
            )
        return value

    def validate(self, attrs: dict) -> dict:
        if self.parent is not None:
            return attrs  # the parent serializer owns question and position
        question = attrs.get("question") or getattr(self.instance, "question", None)
        if question is None:
            raise serializers.ValidationError({"question": "This field is required."})

        max_choices = settings.CARICUE["MAX_CHOICES_PER_QUESTION"]
        siblings = question.choices.exclude(
            pk=self.instance.pk if self.instance else None
        )
        if self.instance is None and siblings.count() >= max_choices:
            raise serializers.ValidationError(
                {"question": f"This question already has {max_choices} choices."}
            )
        if attrs.get("position") is None and self.instance is None:
            attrs["position"] = siblings.count() + 1
        elif (
            attrs.get("position") is not None
            and siblings.filter(position=attrs["position"]).exists()
        ):
            raise serializers.ValidationError(
                {"position": "Another choice already uses this position."}
            )
        return attrs


class QuestionSerializer(serializers.ModelSerializer):
    """Nested inside `ActivitySerializer`, and usable standalone.

    `activity` and `position` are only required for standalone writes; when
    nested, the parent serializer supplies both.
    """

    id = serializers.IntegerField(required=False)
    choices = ChoiceSerializer(many=True, required=False)
    is_auto_scored = serializers.BooleanField(read_only=True)
    activity = serializers.PrimaryKeyRelatedField(
        queryset=Activity.objects.all(), required=False
    )
    position = serializers.IntegerField(required=False, min_value=1)

    class Meta:
        model = Question
        fields = [
            "id",
            "activity",
            "position",
            "prompt",
            "question_type",
            "is_required",
            "collect_confidence",
            "accepted_answers",
            "choices",
            "is_auto_scored",
        ]
        # See the note on `ChoiceSerializer.Meta.validators`: positions are
        # assigned server-side, so the derived unique-together validator would
        # reject valid nested payloads.
        validators = []

    def validate_activity(self, value: Activity) -> Activity:
        if value.teacher_id != self.context["request"].user.pk:
            raise serializers.ValidationError("Activity not found.")
        return value

    def validate_prompt(self, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise serializers.ValidationError("Question prompt is required.")
        return cleaned

    def validate_accepted_answers(self, value) -> list[str]:
        if value in (None, ""):
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError("Accepted answers must be a list.")
        cleaned: list[str] = []
        seen: set[str] = set()
        for item in value:
            if not isinstance(item, str):
                raise serializers.ValidationError("Accepted answers must be strings.")
            text = item.strip()
            if not text:
                continue
            if len(text) > 200:
                raise serializers.ValidationError(
                    "Accepted answers must be 200 characters or fewer."
                )
            key = normalize_text_answer(text)
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(text)
        if len(cleaned) > 20:
            raise serializers.ValidationError("At most 20 accepted answers.")
        return cleaned

    @property
    def _is_nested(self) -> bool:
        return self.parent is not None

    def validate(self, attrs: dict) -> dict:
        if not self._is_nested and self.instance is None and "activity" not in attrs:
            raise serializers.ValidationError({"activity": "This field is required."})

        question_type = attrs.get("question_type") or getattr(
            self.instance, "question_type", None
        )
        choices = attrs.get("choices")
        max_choices = settings.CARICUE["MAX_CHOICES_PER_QUESTION"]

        if question_type == QuestionType.MULTIPLE_CHOICE:
            if choices is None or len(choices) < 2:
                raise serializers.ValidationError(
                    {"choices": "Multiple-choice questions need at least two choices."}
                )
            if len(choices) > max_choices:
                raise serializers.ValidationError(
                    {"choices": f"At most {max_choices} choices per question."}
                )
            if not any(choice.get("is_correct") for choice in choices):
                raise serializers.ValidationError(
                    {"choices": "Mark at least one choice as correct."}
                )
            texts = [choice["text"].strip().lower() for choice in choices]
            if len(set(texts)) != len(texts):
                raise serializers.ValidationError(
                    {"choices": "Choices must be distinct."}
                )
            attrs["accepted_answers"] = []
        else:
            if choices:
                raise serializers.ValidationError(
                    {"choices": f"{question_type} questions cannot have choices."}
                )
            attrs["choices"] = []

        if question_type == QuestionType.CONFIDENCE:
            # A standalone confidence item already *is* the confidence signal.
            attrs["collect_confidence"] = False
            attrs["accepted_answers"] = []
        return attrs

    @transaction.atomic
    def create(self, validated_data: dict) -> Question:
        """Standalone create; the nested path goes through ActivitySerializer."""
        choices = validated_data.pop("choices", []) or []
        validated_data.pop("id", None)
        activity = validated_data["activity"]

        max_questions = settings.CARICUE["MAX_QUESTIONS_PER_ACTIVITY"]
        if activity.questions.count() >= max_questions:
            raise serializers.ValidationError(
                {"activity": f"This activity already has {max_questions} questions."}
            )

        if validated_data.get("position") is None:
            validated_data["position"] = activity.questions.count() + 1
        elif activity.questions.filter(position=validated_data["position"]).exists():
            raise serializers.ValidationError(
                {"position": "Another question already uses this position."}
            )

        question = Question.objects.create(**validated_data)
        for index, choice in enumerate(choices, start=1):
            choice.pop("id", None)
            choice.pop("question", None)
            choice["position"] = index
            Choice.objects.create(question=question, **choice)
        return question

    @transaction.atomic
    def update(self, instance: Question, validated_data: dict) -> Question:
        choices = validated_data.pop("choices", None)
        validated_data.pop("id", None)
        validated_data.pop("activity", None)  # questions never move between activities
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        if choices is not None:
            instance.choices.all().delete()
            for index, choice in enumerate(choices, start=1):
                choice.pop("id", None)
                choice.pop("question", None)
                choice["position"] = index
                Choice.objects.create(question=instance, **choice)
        return instance


class ActivitySerializer(serializers.ModelSerializer):
    """Read/write an activity together with its questions and choices.

    Writes are whole-document: the submitted `questions` array replaces the
    stored one. That keeps the builder UI simple (it owns the array and PUTs
    it back) and makes reordering a matter of renumbering positions.
    """

    questions = QuestionSerializer(many=True, required=False)
    classroom_name = serializers.CharField(source="classroom.name", read_only=True)
    # List views annotate these; writes fall back to a query so a freshly
    # created or updated activity still reports them.
    question_count = serializers.SerializerMethodField()
    open_session_count = serializers.SerializerMethodField()
    follow_up_of_session = serializers.PrimaryKeyRelatedField(read_only=True)
    follow_up_of_session_code = serializers.SerializerMethodField()

    class Meta:
        model = Activity
        fields = [
            "id",
            "classroom",
            "classroom_name",
            "title",
            "topic",
            "status",
            "questions",
            "question_count",
            "open_session_count",
            "follow_up_of_session",
            "follow_up_of_session_code",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "follow_up_of_session",
            "follow_up_of_session_code",
            "created_at",
            "updated_at",
        ]

    def get_question_count(self, activity: Activity) -> int:
        annotated = getattr(activity, "questions_total", None)
        return annotated if annotated is not None else activity.questions.count()

    def get_open_session_count(self, activity: Activity) -> int:
        annotated = getattr(activity, "open_sessions_total", None)
        if annotated is not None:
            return annotated
        return activity.live_sessions.filter(status="open").count()

    def get_follow_up_of_session_code(self, activity: Activity) -> str | None:
        session = activity.follow_up_of_session
        return session.code if session is not None else None

    def validate_title(self, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise serializers.ValidationError("Title is required.")
        return cleaned

    def validate_classroom(self, value: Classroom) -> Classroom:
        if value.teacher_id != self.context["request"].user.pk:
            # Same message a missing id would produce: no cross-tenant probing.
            raise serializers.ValidationError("Class not found.")
        return value

    def validate_questions(self, value: list[dict]) -> list[dict]:
        limits = settings.CARICUE
        if len(value) > limits["MAX_QUESTIONS_PER_ACTIVITY"]:
            raise serializers.ValidationError(
                f"An activity may have at most "
                f"{limits['MAX_QUESTIONS_PER_ACTIVITY']} questions."
            )
        return value

    def validate(self, attrs: dict) -> dict:
        target_status = attrs.get("status") or getattr(
            self.instance, "status", ActivityStatus.DRAFT
        )
        questions = attrs.get("questions")
        if questions is None and self.instance is not None:
            question_total = self.instance.questions.count()
        else:
            question_total = len(questions or [])

        min_questions = settings.CARICUE["MIN_QUESTIONS_PER_ACTIVITY"]
        if target_status == ActivityStatus.PUBLISHED and question_total < min_questions:
            raise serializers.ValidationError(
                {
                    "questions": (
                        f"Add at least {min_questions} question(s) before publishing."
                    )
                }
            )
        return attrs

    @transaction.atomic
    def create(self, validated_data: dict) -> Activity:
        questions = validated_data.pop("questions", [])
        validated_data["teacher"] = self.context["request"].user
        activity = Activity.objects.create(**validated_data)
        self._write_questions(activity, questions)
        return activity

    @transaction.atomic
    def update(self, instance: Activity, validated_data: dict) -> Activity:
        questions = validated_data.pop("questions", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        if questions is not None:
            instance.questions.all().delete()
            self._write_questions(instance, questions)
        return instance

    @staticmethod
    def _write_questions(activity: Activity, questions: list[dict]) -> None:
        for index, payload in enumerate(questions, start=1):
            choices = payload.pop("choices", []) or []
            payload.pop("id", None)
            payload.pop("activity", None)
            payload["position"] = index  # server owns ordering
            question = Question.objects.create(activity=activity, **payload)
            for choice_index, choice in enumerate(choices, start=1):
                choice.pop("id", None)
                choice.pop("question", None)
                choice["position"] = choice_index
                Choice.objects.create(question=question, **choice)


class ActivityListSerializer(serializers.ModelSerializer):
    """Lighter payload for dashboards and list screens."""

    classroom_name = serializers.CharField(source="classroom.name", read_only=True)
    question_count = serializers.IntegerField(
        source="questions_total", read_only=True, default=0
    )

    class Meta:
        model = Activity
        fields = [
            "id",
            "classroom",
            "classroom_name",
            "title",
            "topic",
            "status",
            "question_count",
            "created_at",
            "updated_at",
        ]


class ActivityPreviewQuestionSerializer(serializers.ModelSerializer):
    """Exactly what a student would see. Correctness is never included."""

    choices = serializers.SerializerMethodField()

    class Meta:
        model = Question
        fields = [
            "id",
            "position",
            "prompt",
            "question_type",
            "is_required",
            "collect_confidence",
            "choices",
        ]

    def get_choices(self, question: Question) -> list[dict]:
        return [
            {"id": choice.id, "text": choice.text, "position": choice.position}
            for choice in question.choices.all()
        ]
