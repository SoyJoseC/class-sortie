from __future__ import annotations

from django.conf import settings
from django.db import transaction
from django.db.models import F
from rest_framework import serializers

from caricue.classroom.models import Classroom

from .images import ImageRejected, process_upload
from .models import (
    CHOICE_TYPES,
    SURVEY_ONLY_TYPES,
    Activity,
    ActivityKind,
    ActivityStatus,
    Choice,
    Question,
    QuestionImage,
    QuestionType,
    normalize_text_answer,
)

#: Added to stored positions while renumbering; see `_write_questions`.
POSITION_PARKING_OFFSET = 10_000


def apply_kind_rules(kind: str, attrs: dict) -> None:
    """Enforces what a question may contain given its activity's kind.

    Mutates `attrs` (the validated question data) so a survey can never carry
    an answer key, and raises `ValidationError` for combinations that make no
    sense. Quizzes are marked, so they must say what is right; surveys are
    unmarked, so they must not.
    """
    question_type = attrs.get("question_type")
    choices = attrs.get("choices") or []

    if kind == ActivityKind.SURVEY:
        if question_type == QuestionType.CONFIDENCE:
            raise serializers.ValidationError(
                {"question_type": "Use a rating question in a survey."}
            )
        for choice in choices:
            choice["is_correct"] = False
        attrs["accepted_answers"] = []
        attrs["collect_confidence"] = False
        return

    if question_type in SURVEY_ONLY_TYPES:
        raise serializers.ValidationError(
            {"question_type": "Multi-select and rating questions are only for surveys."}
        )
    if question_type == QuestionType.MULTIPLE_CHOICE and not any(
        choice.get("is_correct") for choice in choices
    ):
        raise serializers.ValidationError(
            {"choices": "Mark at least one choice as correct."}
        )


def sync_choices(question: Question, choices: list[dict]) -> None:
    """Replaces `question`'s choices with `choices`, keeping rows by `id`.

    Updating in place keeps `Response.selected_choice` pointing at the same
    row, so editing a choice's wording does not blank out earlier answers.
    """
    existing = {c.pk: c for c in question.choices.all()}
    matches: list[tuple[dict, Choice | None]] = []
    claimed: set[int] = set()
    for payload in choices:
        choice_id = payload.get("id")
        choice = existing.get(choice_id) if choice_id not in claimed else None
        if choice is not None:
            claimed.add(choice.pk)
        matches.append((payload, choice))

    question.choices.exclude(pk__in=claimed).delete()
    Choice.objects.filter(pk__in=claimed).update(
        position=F("position") + POSITION_PARKING_OFFSET
    )
    for index, (payload, choice) in enumerate(matches, start=1):
        data = {
            key: value
            for key, value in payload.items()
            if key not in {"id", "question", "position"}
        }
        if choice is None:
            Choice.objects.create(question=question, position=index, **data)
        else:
            for field, value in data.items():
                setattr(choice, field, value)
            choice.position = index
            choice.save()


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
        if value.question_type not in CHOICE_TYPES:
            raise serializers.ValidationError(
                "Only multiple-choice and multi-select questions can have choices."
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


class QuestionImageSerializer(serializers.ModelSerializer):
    """Upload (write) and describe (read) one question image."""

    file = serializers.FileField(write_only=True)
    url = serializers.CharField(read_only=True)

    class Meta:
        model = QuestionImage
        fields = ["id", "file", "url", "width", "height", "created_at"]
        read_only_fields = ["id", "url", "width", "height", "created_at"]

    def validate_file(self, upload):
        try:
            processed = process_upload(upload)
        except ImageRejected as exc:
            raise serializers.ValidationError(str(exc)) from exc
        # The stored name is random; only the extension is carried over.
        processed.content.name = f"upload{processed.extension}"
        return processed.content

    def create(self, validated_data: dict) -> QuestionImage:
        validated_data["teacher"] = self.context["request"].user
        return super().create(validated_data)


class QuestionSerializer(serializers.ModelSerializer):
    """Nested inside `ActivitySerializer`, and usable standalone.

    `activity` and `position` are only required for standalone writes; when
    nested, the parent serializer supplies both.
    """

    id = serializers.IntegerField(required=False)
    choices = ChoiceSerializer(many=True, required=False)
    is_auto_scored = serializers.BooleanField(read_only=True)
    response_count = serializers.SerializerMethodField()
    activity = serializers.PrimaryKeyRelatedField(
        queryset=Activity.objects.all(), required=False
    )
    position = serializers.IntegerField(required=False, min_value=1)
    # Upload-first: the builder POSTs the file to /api/question-images/, then
    # refers to it here. `null` detaches the picture.
    image_id = serializers.PrimaryKeyRelatedField(
        source="image",
        queryset=QuestionImage.objects.all(),
        required=False,
        allow_null=True,
    )
    image_url = serializers.CharField(read_only=True, allow_null=True)

    class Meta:
        model = Question
        fields = [
            "id",
            "activity",
            "position",
            "prompt",
            "image_id",
            "image_url",
            "image_alt",
            "question_type",
            "rating_low_label",
            "rating_high_label",
            "is_required",
            "collect_confidence",
            "accepted_answers",
            "choices",
            "is_auto_scored",
            "response_count",
        ]
        # See the note on `ChoiceSerializer.Meta.validators`: positions are
        # assigned server-side, so the derived unique-together validator would
        # reject valid nested payloads.
        validators = []

    def get_response_count(self, question: Question) -> int:
        annotated = getattr(question, "responses_total", None)
        if annotated is not None:
            return annotated
        if question.pk is None:
            return 0
        return question.responses.count()

    def validate_activity(self, value: Activity) -> Activity:
        if value.teacher_id != self.context["request"].user.pk:
            raise serializers.ValidationError("Activity not found.")
        return value

    def validate_prompt(self, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise serializers.ValidationError("Question prompt is required.")
        return cleaned

    def validate_image_id(self, value: QuestionImage | None) -> QuestionImage | None:
        if value is not None and value.teacher_id != self.context["request"].user.pk:
            # Same message a missing id would produce: no cross-tenant probing.
            raise serializers.ValidationError("Image not found.")
        return value

    def validate_image_alt(self, value: str) -> str:
        return " ".join((value or "").split())

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

        if "image" in attrs and attrs["image"] is None:
            attrs["image_alt"] = ""  # alt text without a picture is meaningless

        question_type = attrs.get("question_type") or getattr(
            self.instance, "question_type", None
        )
        choices = attrs.get("choices")
        max_choices = settings.CARICUE["MAX_CHOICES_PER_QUESTION"]

        if question_type in CHOICE_TYPES:
            label = (
                "Multiple-choice"
                if question_type == QuestionType.MULTIPLE_CHOICE
                else "Multi-select"
            )
            if choices is None or len(choices) < 2:
                raise serializers.ValidationError(
                    {"choices": f"{label} questions need at least two choices."}
                )
            if len(choices) > max_choices:
                raise serializers.ValidationError(
                    {"choices": f"At most {max_choices} choices per question."}
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
        if question_type != QuestionType.RATING:
            attrs["rating_low_label"] = ""
            attrs["rating_high_label"] = ""

        # Whether the answer key is required depends on the activity's kind.
        # Standalone writes know their activity; nested ones are checked by
        # `ActivitySerializer.validate`.
        if not self._is_nested:
            activity = attrs.get("activity") or getattr(self.instance, "activity", None)
            if activity is not None:
                try:
                    apply_kind_rules(activity.kind, attrs)
                except serializers.ValidationError as exc:
                    raise serializers.ValidationError(exc.detail) from exc
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
        sync_choices(question, choices)
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
            sync_choices(instance, choices)
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
    review_item = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Activity
        fields = [
            "id",
            "classroom",
            "classroom_name",
            "title",
            "topic",
            "status",
            "kind",
            "questions",
            "question_count",
            "open_session_count",
            "follow_up_of_session",
            "follow_up_of_session_code",
            "review_item",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "follow_up_of_session",
            "follow_up_of_session_code",
            "review_item",
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

    def validate_kind(self, value: str) -> str:
        if (
            self.instance is not None
            and value != self.instance.kind
            and self.instance.live_sessions.exists()
        ):
            raise serializers.ValidationError(
                "A quiz and a survey are scored differently, so the kind cannot "
                "change once the activity has been launched. Duplicate it instead."
            )
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

        kind = attrs.get("kind") or getattr(self.instance, "kind", ActivityKind.QUIZ)
        for number, question in enumerate(questions or [], start=1):
            try:
                apply_kind_rules(kind, question)
            except serializers.ValidationError as exc:
                detail = exc.detail
                message = (
                    next(iter(detail.values())) if isinstance(detail, dict) else detail
                )
                if isinstance(message, list):
                    message = message[0]
                raise serializers.ValidationError(
                    {"questions": f"Question {number}: {message}"}
                ) from exc

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
            self._write_questions(instance, questions)
        return instance

    @staticmethod
    def _write_questions(activity: Activity, questions: list[dict]) -> None:
        """Brings the stored questions in line with the submitted array.

        Questions are matched by `id` and updated in place, so student
        responses, follow-up lineage and attached images survive an edit.
        Only questions missing from the payload are deleted. An `id` that
        does not belong to this activity is ignored and treated as a new
        question, so one teacher cannot reach another's rows through it.
        """
        existing = {q.pk: q for q in activity.questions.all()}
        matches: list[tuple[dict, Question | None]] = []
        claimed: set[int] = set()
        for payload in questions:
            question_id = payload.get("id")
            question = existing.get(question_id) if question_id not in claimed else None
            if question is not None:
                claimed.add(question.pk)
            matches.append((payload, question))

        activity.questions.exclude(pk__in=claimed).delete()
        # Park survivors out of the way so renumbering cannot collide with the
        # `(activity, position)` unique constraint (e.g. when reordering).
        Question.objects.filter(pk__in=claimed).update(
            position=F("position") + POSITION_PARKING_OFFSET
        )

        for index, (payload, question) in enumerate(matches, start=1):
            choices = payload.pop("choices", []) or []
            payload.pop("id", None)
            payload.pop("activity", None)
            payload["position"] = index  # server owns ordering
            if question is None:
                question = Question.objects.create(activity=activity, **payload)
            else:
                for field, value in payload.items():
                    setattr(question, field, value)
                question.save()
            sync_choices(question, choices)


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
            "kind",
            "question_count",
            "created_at",
            "updated_at",
        ]


class ActivityPreviewQuestionSerializer(serializers.ModelSerializer):
    """Exactly what a student would see. Correctness is never included."""

    choices = serializers.SerializerMethodField()
    image_url = serializers.CharField(read_only=True, allow_null=True)

    class Meta:
        model = Question
        fields = [
            "id",
            "position",
            "prompt",
            "image_url",
            "image_alt",
            "question_type",
            "rating_low_label",
            "rating_high_label",
            "is_required",
            "collect_confidence",
            "choices",
        ]

    def get_choices(self, question: Question) -> list[dict]:
        return [
            {"id": choice.id, "text": choice.text, "position": choice.position}
            for choice in question.choices.all()
        ]
