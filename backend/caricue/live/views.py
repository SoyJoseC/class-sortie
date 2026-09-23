from __future__ import annotations

from django.conf import settings
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import (
    action,
    api_view,
    authentication_classes,
    permission_classes,
    throttle_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response as ApiResponse
from rest_framework.views import APIView

from caricue.accounts.student_account import get_student_account
from caricue.activities.follow_up import create_follow_up_activity
from caricue.core.permissions import OwnedQuerysetMixin
from caricue.core.throttling import (
    PublicJoinThrottle,
    PublicLookupThrottle,
    PublicSubmitThrottle,
)
from caricue.insights.comparison import build_session_comparison
from caricue.insights.misconceptions import build_misconception_cards
from caricue.insights.providers import generate_suggestions
from caricue.insights.service import build_session_insights
from caricue.insights.topics import topic_for_session

from .models import (
    IdentityMode,
    LiveSession,
    Participant,
    SessionStatus,
    TeacherReflection,
)
from .serializers import (
    LiveSessionSerializer,
    ParticipantSerializer,
    PublicJoinSerializer,
    PublicSessionSerializer,
    PublicSubmitSerializer,
    ShortCodeLookupSerializer,
    TeacherReflectionSerializer,
)
from .services import SubmissionError, close_session, join_session, submit_responses


class LiveSessionViewSet(OwnedQuerysetMixin, viewsets.ReadOnlyModelViewSet):
    """Teacher-facing session read access plus close/dashboard/results."""

    serializer_class = LiveSessionSerializer
    queryset = LiveSession.objects.select_related("activity", "classroom", "reflection")
    owner_field = "activity__teacher"

    def get_queryset(self):
        queryset = super().get_queryset()
        status_filter = self.request.query_params.get("status")
        if status_filter in SessionStatus.values:
            queryset = queryset.filter(status=status_filter)
        classroom_id = self.request.query_params.get("classroom")
        if classroom_id:
            queryset = queryset.filter(classroom_id=classroom_id)
        activity_id = self.request.query_params.get("activity")
        if activity_id:
            queryset = queryset.filter(activity_id=activity_id)
        return queryset

    @action(detail=True, methods=["post"])
    def close(self, request: Request, pk: str | None = None) -> ApiResponse:
        session = self.get_object()
        if not session.is_open:
            return ApiResponse(
                {
                    "detail": "This session is already closed.",
                    "code": "already_closed",
                    "errors": {},
                },
                status=status.HTTP_409_CONFLICT,
            )
        close_session(session)
        session.refresh_from_db()
        return ApiResponse(
            LiveSessionSerializer(session, context={"request": request}).data
        )

    @action(detail=True, methods=["get"])
    def dashboard(self, request: Request, pk: str | None = None) -> ApiResponse:
        """The polled live view.

        Deterministic figures are returned under `facts`; provider output is
        returned under `suggestions` and is only computed once there is
        something to reason about, keeping the 3-5s poll cheap.
        """
        session = self.get_object()
        insights = build_session_insights(session)
        suggestions = (
            generate_suggestions(insights) if insights.submitted_count > 0 else []
        )
        misconception_cards = (
            [card.as_dict() for card in build_misconception_cards(insights)]
            if insights.submitted_count > 0
            else []
        )
        comparison = (
            build_session_comparison(session)
            if session.status == SessionStatus.CLOSED
            else None
        )
        return ApiResponse(
            {
                "session": LiveSessionSerializer(
                    session, context={"request": request}
                ).data,
                "facts": {"kind": "fact", **insights.as_dict()},
                "suggestions": suggestions,
                "misconception_cards": misconception_cards,
                "comparison": comparison.as_dict() if comparison else None,
                "poll_interval_seconds": settings.CARICUE["DASHBOARD_POLL_SECONDS"],
            }
        )

    @action(detail=True, methods=["get"])
    def results(self, request: Request, pk: str | None = None) -> ApiResponse:
        """Full post-session results, including per-participant detail."""
        session = self.get_object()
        insights = build_session_insights(session)
        participants = session.participants.select_related("student").prefetch_related(
            "responses__question", "responses__selected_choice"
        )
        reflection = getattr(session, "reflection", None)
        misconception_cards = [
            card.as_dict() for card in build_misconception_cards(insights)
        ]
        comparison = build_session_comparison(session)
        return ApiResponse(
            {
                "session": LiveSessionSerializer(
                    session, context={"request": request}
                ).data,
                "facts": {"kind": "fact", **insights.as_dict()},
                "suggestions": generate_suggestions(insights),
                "misconception_cards": misconception_cards,
                "comparison": comparison.as_dict() if comparison else None,
                "participants": ParticipantSerializer(participants, many=True).data,
                "reflection": (
                    TeacherReflectionSerializer(
                        reflection, context={"request": request}
                    ).data
                    if reflection is not None
                    else None
                ),
            }
        )

    @action(detail=True, methods=["get"], url_path="misconceptions")
    def misconceptions(self, request: Request, pk: str | None = None) -> ApiResponse:
        session = self.get_object()
        insights = build_session_insights(session)
        cards = build_misconception_cards(insights)
        return ApiResponse({"misconception_cards": [c.as_dict() for c in cards]})

    @action(detail=True, methods=["post"], url_path="follow-up-activity")
    def follow_up_activity(self, request: Request, pk: str | None = None) -> ApiResponse:
        session = self.get_object()
        question_ids = request.data.get("question_ids") or request.data.get(
            "card_ids"
        )
        include_confidence = request.data.get("include_confidence", True)
        try:
            activity = create_follow_up_activity(
                session,
                request.user,
                question_ids=question_ids,
                include_confidence=include_confidence,
            )
        except ValueError as exc:
            return ApiResponse(
                {"detail": str(exc), "code": "invalid", "errors": {}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return ApiResponse({"activity_id": activity.pk}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def participants(self, request: Request, pk: str | None = None) -> ApiResponse:
        session = self.get_object()
        queryset = session.participants.select_related("student").prefetch_related(
            "responses__question", "responses__selected_choice"
        )
        return ApiResponse(ParticipantSerializer(queryset, many=True).data)


class TeacherReflectionViewSet(OwnedQuerysetMixin, viewsets.ModelViewSet):
    serializer_class = TeacherReflectionSerializer
    queryset = TeacherReflection.objects.select_related(
        "live_session", "live_session__activity"
    )
    owner_field = "live_session__activity__teacher"

    def get_queryset(self):
        queryset = super().get_queryset()
        session_id = self.request.query_params.get("live_session")
        if session_id:
            queryset = queryset.filter(live_session_id=session_id)
        return queryset


# --------------------------------------------------------------------------- #
# Public student endpoints
# --------------------------------------------------------------------------- #
def _get_open_or_any_session(public_token: str) -> LiveSession:
    return get_object_or_404(
        LiveSession.objects.select_related("activity", "classroom"),
        public_token=public_token,
    )


def _submission_error_response(exc: SubmissionError) -> ApiResponse:
    http_status = (
        status.HTTP_409_CONFLICT
        if exc.code in {"already_submitted", "session_closed", "name_taken"}
        else status.HTTP_400_BAD_REQUEST
    )
    return ApiResponse(
        {"detail": exc.message, "code": exc.code, "errors": {}},
        status=http_status,
    )


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([PublicLookupThrottle])
def public_code_lookup(request: Request) -> ApiResponse:
    """Resolves a short code to a session token.

    Short codes are guessable by design (a teacher reads them aloud), so this
    endpoint is the most heavily throttled in the API and only ever resolves
    codes for sessions that are currently open.
    """
    serializer = ShortCodeLookupSerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)
    code = serializer.validated_data["code"]

    session = LiveSession.objects.filter(code=code, status=SessionStatus.OPEN).first()
    if session is None:
        return ApiResponse(
            {
                "detail": "No open session found for that code.",
                "code": "session_not_found",
                "errors": {},
            },
            status=status.HTTP_404_NOT_FOUND,
        )
    return ApiResponse(
        {"public_token": session.public_token, "join_url": session.join_url}
    )


class PublicSessionView(APIView):
    """The activity as a student sees it, addressed by public token."""

    authentication_classes: list = []
    permission_classes = [AllowAny]
    throttle_classes = [PublicLookupThrottle]

    def get(self, request: Request, public_token: str) -> ApiResponse:
        session = _get_open_or_any_session(public_token)
        data = PublicSessionSerializer(session).data
        if not session.is_open:
            # Still described, so the student sees a clear "closed" screen
            # rather than a dead link, but questions are withheld.
            data["questions"] = []
        return ApiResponse(data)


class PublicJoinView(APIView):
    authentication_classes: list = []
    permission_classes = [AllowAny]
    throttle_classes = [PublicJoinThrottle]

    def post(self, request: Request, public_token: str) -> ApiResponse:
        session = _get_open_or_any_session(public_token)
        if session.identity_mode == IdentityMode.GOOGLE_ACCOUNT:
            account = get_student_account(request)
            if account is None:
                return ApiResponse(
                    {
                        "detail": "Sign in with your school Google account to join.",
                        "code": "google_sign_in_required",
                        "errors": {},
                    },
                    status=status.HTTP_401_UNAUTHORIZED,
                )
            identifier = account.email
        else:
            serializer = PublicJoinSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            identifier = serializer.validated_data["identifier"]
        try:
            result = join_session(session=session, identifier=identifier)
        except SubmissionError as exc:
            return _submission_error_response(exc)

        return ApiResponse(
            {
                # The token is the participant's only credential; it is
                # returned once, to the joining device.
                "participant_token": result.participant.participant_token,
                "display_label": result.participant.label,
                "resumed": result.resumed,
                "session": PublicSessionSerializer(session).data,
            },
            status=status.HTTP_200_OK if result.resumed else status.HTTP_201_CREATED,
        )


class PublicSubmitView(APIView):
    authentication_classes: list = []
    permission_classes = [AllowAny]
    throttle_classes = [PublicSubmitThrottle]

    def post(self, request: Request, public_token: str) -> ApiResponse:
        session = _get_open_or_any_session(public_token)
        serializer = PublicSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        participant = Participant.objects.filter(
            live_session=session,
            participant_token=serializer.validated_data["participant_token"],
        ).first()
        if participant is None:
            return ApiResponse(
                {
                    "detail": "Please rejoin the session.",
                    "code": "participant_missing",
                    "errors": {},
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            submitted = submit_responses(
                session=session,
                participant=participant,
                answers=serializer.validated_data["answers"],
            )
        except SubmissionError as exc:
            return _submission_error_response(exc)

        return ApiResponse(
            {
                "detail": "Your answers were submitted. Thank you!",
                "submitted_at": submitted.submitted_at,
                "answer_count": submitted.responses.count(),
                "activity_title": session.activity.title,
            },
            status=status.HTTP_201_CREATED,
        )


# --------------------------------------------------------------------------- #
# Teacher dashboard summary
# --------------------------------------------------------------------------- #
class TeacherOverviewView(APIView):
    """One request that fills the teacher's home screen."""

    def get(self, request: Request) -> ApiResponse:
        from caricue.activities.models import Activity
        from caricue.activities.serializers import ActivityListSerializer
        from caricue.classroom.models import Classroom
        from caricue.classroom.serializers import ClassroomSerializer

        teacher = request.user

        classrooms = (
            Classroom.objects.filter(teacher=teacher)
            .annotate(
                enrolled_count=Count(
                    "enrollments",
                    filter=Q(enrollments__is_active=True),
                    distinct=True,
                ),
                activities_total=Count("activities", distinct=True),
            )
            .order_by("name")
        )
        activities = (
            Activity.objects.filter(teacher=teacher)
            .select_related("classroom")
            .annotate(questions_total=Count("questions", distinct=True))
            .order_by("-created_at")[:5]
        )
        open_sessions = LiveSession.objects.filter(
            activity__teacher=teacher, status=SessionStatus.OPEN
        ).select_related("activity", "classroom")
        recent_sessions = (
            LiveSession.objects.filter(activity__teacher=teacher)
            .select_related("activity", "classroom", "reflection")
            .order_by("-started_at")[:5]
        )

        recent_results = []
        for session in recent_sessions:
            insights = build_session_insights(session)
            cards = build_misconception_cards(insights)
            comparison = build_session_comparison(session)
            recent_results.append(
                {
                    "session": LiveSessionSerializer(
                        session, context={"request": request}
                    ).data,
                    "submitted_count": insights.submitted_count,
                    "completion_percentage": insights.completion_percentage,
                    "overall_correctness_percentage": (
                        insights.overall_correctness_percentage
                    ),
                    "average_confidence": insights.average_confidence,
                    "needs_attention_count": len(insights.needs_attention),
                    "misconception_count": len(cards),
                    "has_comparison": comparison is not None,
                }
            )

        pending_followups = _pending_followups(teacher)

        context = {"request": request}
        return ApiResponse(
            {
                "teacher": {
                    "id": teacher.pk,
                    "full_name": teacher.full_name,
                    "email": teacher.email,
                    "school_name": teacher.school_name,
                },
                "classrooms": ClassroomSerializer(
                    classrooms, many=True, context=context
                ).data,
                "recent_activities": ActivityListSerializer(
                    activities, many=True, context=context
                ).data,
                "open_sessions": LiveSessionSerializer(
                    open_sessions, many=True, context=context
                ).data,
                "recent_results": recent_results,
                "pending_followups": pending_followups,
                "counts": {
                    "classrooms": classrooms.count(),
                    "activities": Activity.objects.filter(teacher=teacher).count(),
                    "open_sessions": open_sessions.count(),
                    "students": teacher.students.filter(is_active=True).count(),
                },
            }
        )


def _pending_followups(teacher) -> list[dict]:
    """Closed sessions with changed plans that may need a follow-up check."""
    from datetime import timedelta

    from caricue.live.models import PlanImpact

    nudge_days = settings.CARICUE["FOLLOWUP_NUDGE_DAYS"]
    cutoff = timezone.now() - timedelta(days=nudge_days)

    sessions = (
        LiveSession.objects.filter(
            activity__teacher=teacher,
            status=SessionStatus.CLOSED,
            reflection__plan_impact=PlanImpact.CHANGED,
            closed_at__lte=cutoff,
        )
        .select_related("activity", "classroom", "reflection")
        .order_by("-closed_at")
    )

    pending: list[dict] = []
    seen_topics: set[tuple[int, str]] = set()

    for session in sessions:
        topic_key = (session.classroom_id, topic_for_session(session))
        if topic_key in seen_topics:
            continue

        newer = LiveSession.objects.filter(
            classroom=session.classroom,
            status=SessionStatus.CLOSED,
            closed_at__gt=session.closed_at,
        )
        has_newer_same_topic = any(
            topic_for_session(s) == topic_key[1]
            for s in newer.select_related("activity")
        )
        if has_newer_same_topic:
            continue

        seen_topics.add(topic_key)
        insights = build_session_insights(session)
        cards = build_misconception_cards(insights)
        reflection = session.reflection
        days_since = (timezone.now() - session.closed_at).days if session.closed_at else 0

        pending.append(
            {
                "classroom_id": session.classroom_id,
                "classroom_name": session.classroom.name,
                "topic": session.activity.topic or session.activity.title,
                "last_session_id": session.pk,
                "last_session_code": session.code,
                "closed_at": (
                    session.closed_at.isoformat() if session.closed_at else None
                ),
                "days_since": days_since,
                "primary_gap": reflection.primary_gap if reflection else "",
                "plan_impact": reflection.plan_impact if reflection else "",
                "top_misconception_title": (
                    cards[0].suggestion.title if cards and cards[0].suggestion else ""
                ),
            }
        )

    return pending
