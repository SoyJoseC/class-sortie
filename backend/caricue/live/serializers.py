from __future__ import annotations

from django.conf import settings
from rest_framework import serializers

from caricue.activities.models import CONFIDENCE_MAX, CONFIDENCE_MIN, Question

from .models import (
    IdentityMode,
    LiveSession,
    Participant,
    Response,
    TeacherReflection,
)


class LiveSessionSerializer(serializers.ModelSerializer):
    """Teacher-facing session view, including the join/QR details."""

    activity_title = serializers.CharField(source="activity.title", read_only=True)
    activity_topic = serializers.CharField(source="activity.topic", read_only=True)
    classroom_name = serializers.CharField(source="classroom.name", read_only=True)
    join_url = serializers.CharField(read_only=True)
    roster_size = serializers.IntegerField(read_only=True)
    participant_count = serializers.SerializerMethodField()
    submitted_count = serializers.SerializerMethodField()
    has_reflection = serializers.SerializerMethodField()
    poll_interval_seconds = serializers.SerializerMethodField()

    class Meta:
        model = LiveSession
        fields = [
            "id",
            "activity",
            "activity_title",
            "activity_topic",
            "classroom",
            "classroom_name",
            "code",
            "public_token",
            "join_url",
            "status",
            "identity_mode",
            "roster_size",
            "participant_count",
            "submitted_count",
            "has_reflection",
            "poll_interval_seconds",
            "started_at",
            "closed_at",
        ]
        read_only_fields = fields

    def get_participant_count(self, session: LiveSession) -> int:
        return session.participants.count()

    def get_submitted_count(self, session: LiveSession) -> int:
        return session.participants.filter(submitted_at__isnull=False).count()

    def get_has_reflection(self, session: LiveSession) -> bool:
        return hasattr(session, "reflection")

    def get_poll_interval_seconds(self, session: LiveSession) -> int:
        return settings.CARICUE["DASHBOARD_POLL_SECONDS"]


class LaunchSessionSerializer(serializers.Serializer):
    identity_mode = serializers.ChoiceField(
        choices=IdentityMode.choices,
        required=False,
        default=IdentityMode.DISPLAY_NAME,
    )


class TeacherReflectionSerializer(serializers.ModelSerializer):
    session_code = serializers.CharField(source="live_session.code", read_only=True)
    activity_title = serializers.CharField(
        source="live_session.activity.title", read_only=True
    )

    class Meta:
        model = TeacherReflection
        fields = [
            "id",
            "live_session",
            "session_code",
            "activity_title",
            "primary_gap",
            "plan_impact",
            "planned_action",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_live_session(self, value: LiveSession) -> LiveSession:
        if value.activity.teacher_id != self.context["request"].user.pk:
            raise serializers.ValidationError("Session not found.")
        return value

    def validate_primary_gap(self, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise serializers.ValidationError("Name the main gap this check surfaced.")
        return cleaned

    def validate_planned_action(self, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise serializers.ValidationError(
                "Record what you will review, reteach or reinforce."
            )
        return cleaned

    def validate(self, attrs: dict) -> dict:
        session = attrs.get("live_session") or getattr(
            self.instance, "live_session", None
        )
        if (
            session is not None
            and self.instance is None
            and TeacherReflection.objects.filter(live_session=session).exists()
        ):
            raise serializers.ValidationError(
                {"live_session": "This session already has a reflection."}
            )
        return attrs


class ParticipantResponseSerializer(serializers.ModelSerializer):
    """Full response detail for the teacher's results screen."""

    question_position = serializers.IntegerField(
        source="question.position", read_only=True
    )
    question_prompt = serializers.CharField(source="question.prompt", read_only=True)
    question_type = serializers.CharField(source="question.question_type", read_only=True)
    selected_choice_text = serializers.CharField(
        source="selected_choice.text", read_only=True, default=None
    )

    class Meta:
        model = Response
        fields = [
            "id",
            "question",
            "question_position",
            "question_prompt",
            "question_type",
            "selected_choice",
            "selected_choice_text",
            "text_response",
            "confidence_value",
            "is_correct",
            "created_at",
        ]
        read_only_fields = fields


class ParticipantSerializer(serializers.ModelSerializer):
    label = serializers.CharField(read_only=True)
    has_submitted = serializers.BooleanField(read_only=True)
    responses = ParticipantResponseSerializer(many=True, read_only=True)

    class Meta:
        model = Participant
        # participant_token is intentionally absent: it is a credential.
        fields = [
            "id",
            "label",
            "display_name",
            "student",
            "has_submitted",
            "submitted_at",
            "created_at",
            "responses",
        ]
        read_only_fields = fields


# --------------------------------------------------------------------------- #
# Public (student-facing) serializers
# --------------------------------------------------------------------------- #
class PublicChoiceSerializer(serializers.Serializer):
    """No `is_correct`. The answer key never reaches a student device."""

    id = serializers.IntegerField(read_only=True)
    text = serializers.CharField(read_only=True)
    position = serializers.IntegerField(read_only=True)


class PublicQuestionSerializer(serializers.ModelSerializer):
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
        read_only_fields = fields

    def get_choices(self, question: Question) -> list[dict]:
        return PublicChoiceSerializer(question.choices.all(), many=True).data


class PublicSessionSerializer(serializers.ModelSerializer):
    """What a student's device is allowed to know about a session.

    Excludes the roster, participant list, response data, teacher identity and
    every correctness flag.
    """

    activity_title = serializers.CharField(source="activity.title", read_only=True)
    activity_topic = serializers.CharField(source="activity.topic", read_only=True)
    class_name = serializers.CharField(source="classroom.name", read_only=True)
    questions = serializers.SerializerMethodField()
    is_open = serializers.BooleanField(read_only=True)
    confidence_scale = serializers.SerializerMethodField()

    class Meta:
        model = LiveSession
        fields = [
            "public_token",
            "code",
            "status",
            "is_open",
            "identity_mode",
            "activity_title",
            "activity_topic",
            "class_name",
            "questions",
            "confidence_scale",
        ]
        read_only_fields = fields

    def get_questions(self, session: LiveSession) -> list[dict]:
        questions = session.activity.questions.prefetch_related("choices").order_by(
            "position"
        )
        return PublicQuestionSerializer(questions, many=True).data

    def get_confidence_scale(self, session: LiveSession) -> dict:
        return {"min": CONFIDENCE_MIN, "max": CONFIDENCE_MAX}


class PublicJoinSerializer(serializers.Serializer):
    identifier = serializers.CharField(max_length=80, allow_blank=False)

    def validate_identifier(self, value: str) -> str:
        cleaned = " ".join((value or "").split())
        if not cleaned:
            raise serializers.ValidationError("Please enter your name to join.")
        return cleaned


class PublicAnswerSerializer(serializers.Serializer):
    question = serializers.IntegerField()
    selected_choice = serializers.IntegerField(required=False, allow_null=True)
    text_response = serializers.CharField(
        required=False, allow_blank=True, max_length=1000
    )
    confidence_value = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=CONFIDENCE_MIN,
        max_value=CONFIDENCE_MAX,
    )


class PublicSubmitSerializer(serializers.Serializer):
    participant_token = serializers.CharField(max_length=64)
    answers = serializers.ListField(
        child=PublicAnswerSerializer(),
        allow_empty=False,
        max_length=settings.CARICUE["MAX_QUESTIONS_PER_ACTIVITY"],
    )


class ShortCodeLookupSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=12)

    def validate_code(self, value: str) -> str:
        cleaned = (value or "").strip().upper().replace(" ", "").replace("-", "")
        if not cleaned.isalnum():
            raise serializers.ValidationError("Session codes are letters and numbers.")
        return cleaned
