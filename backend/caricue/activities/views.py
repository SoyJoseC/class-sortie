from __future__ import annotations

from django.db.models import Count, Prefetch, Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from caricue.core.permissions import OwnedQuerysetMixin
from caricue.live.models import LiveSession, SessionStatus
from caricue.live.serializers import LiveSessionSerializer
from caricue.live.services import launch_session

from .models import Activity, Choice, Question
from .serializers import (
    ActivityListSerializer,
    ActivityPreviewQuestionSerializer,
    ActivitySerializer,
    ChoiceSerializer,
    QuestionSerializer,
)


class ActivityViewSet(OwnedQuerysetMixin, viewsets.ModelViewSet):
    serializer_class = ActivitySerializer
    queryset = Activity.objects.select_related("classroom")

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .annotate(
                # Suffixed so they do not shadow `Activity.question_count`.
                questions_total=Count("questions", distinct=True),
                open_sessions_total=Count(
                    "live_sessions",
                    filter=Q(live_sessions__status=SessionStatus.OPEN),
                    distinct=True,
                ),
            )
            .prefetch_related(
                Prefetch(
                    "questions",
                    queryset=Question.objects.prefetch_related("choices"),
                )
            )
            .order_by("-created_at")
        )

    def get_serializer_class(self):
        if self.action == "list":
            return ActivityListSerializer
        return ActivitySerializer

    @action(detail=True, methods=["get"])
    def preview(self, request: Request, pk: str | None = None) -> Response:
        """Renders the activity the way a student will see it."""
        activity = self.get_object()
        questions = activity.questions.prefetch_related("choices")
        return Response(
            {
                "activity": {
                    "id": activity.id,
                    "title": activity.title,
                    "topic": activity.topic,
                    "status": activity.status,
                },
                "questions": ActivityPreviewQuestionSerializer(questions, many=True).data,
            }
        )

    @action(detail=True, methods=["post"])
    def launch(self, request: Request, pk: str | None = None) -> Response:
        """Publishes the activity and opens a live session for students."""
        activity = self.get_object()
        identity_mode = request.data.get("identity_mode")
        session, error = launch_session(
            activity=activity,
            identity_mode=identity_mode,
        )
        if error:
            return Response(
                {"detail": error, "code": "not_launchable", "errors": {}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            LiveSessionSerializer(session, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["get"], url_path="sessions")
    def sessions(self, request: Request, pk: str | None = None) -> Response:
        activity = self.get_object()
        queryset = LiveSession.objects.filter(activity=activity).select_related(
            "activity", "classroom"
        )
        return Response(
            LiveSessionSerializer(queryset, many=True, context={"request": request}).data
        )


class QuestionViewSet(OwnedQuerysetMixin, viewsets.ModelViewSet):
    """Direct question access.

    The builder normally saves whole activities, but individual question
    edits are useful for scripted use and for the API surface to be complete.
    """

    serializer_class = QuestionSerializer
    queryset = Question.objects.select_related("activity").prefetch_related("choices")
    owner_field = "activity__teacher"

    def get_queryset(self):
        queryset = super().get_queryset()
        activity_id = self.request.query_params.get("activity")
        if activity_id:
            queryset = queryset.filter(activity_id=activity_id)
        return queryset


class ChoiceViewSet(OwnedQuerysetMixin, viewsets.ModelViewSet):
    serializer_class = ChoiceSerializer
    queryset = Choice.objects.select_related("question__activity")
    owner_field = "question__activity__teacher"

    def get_queryset(self):
        queryset = super().get_queryset()
        question_id = self.request.query_params.get("question")
        if question_id:
            queryset = queryset.filter(question_id=question_id)
        return queryset
