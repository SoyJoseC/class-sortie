from __future__ import annotations

from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import (
    action,
    api_view,
    authentication_classes,
    permission_classes,
    throttle_classes,
)
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from caricue.accounts.student_account import get_student_account
from caricue.core.permissions import OwnedQuerysetMixin
from caricue.core.throttling import PublicJoinThrottle, PublicLookupThrottle
from caricue.insights.comparison import build_topic_timeline

from .class_join import ClassJoinError, join_class_via_invite
from .csv_import import SAMPLE_CSV, RosterImportError, import_roster_csv
from .models import Classroom, Enrollment, Student
from .serializers import (
    AddStudentToClassSerializer,
    ClassroomSerializer,
    EnrollmentSerializer,
    RosterImportSerializer,
    StudentSerializer,
)


class ClassroomViewSet(OwnedQuerysetMixin, viewsets.ModelViewSet):
    """CRUD for the signed-in teacher's classes, plus roster operations."""

    serializer_class = ClassroomSerializer
    queryset = Classroom.objects.all()

    def get_queryset(self):
        # Annotation aliases are suffixed so they never shadow the model
        # properties of the same concept (`Classroom.roster_size`).
        return (
            super()
            .get_queryset()
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

    @action(detail=True, methods=["get"], url_path="roster")
    def roster(self, request: Request, pk: str | None = None) -> Response:
        """The teacher-only roster for a class. Never exposed publicly."""
        classroom = self.get_object()
        enrollments = (
            Enrollment.objects.filter(classroom=classroom)
            .select_related("student")
            .order_by("student__display_name")
        )
        serializer = EnrollmentSerializer(
            enrollments, many=True, context=self.get_serializer_context()
        )
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="students")
    def add_student(self, request: Request, pk: str | None = None) -> Response:
        """Creates a student for this teacher and enrols them in this class."""
        classroom = self.get_object()
        serializer = AddStudentToClassSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        identifier = data.get("school_identifier", "")
        if identifier:
            existing = Student.objects.filter(
                teacher=request.user, school_identifier__iexact=identifier
            ).first()
            if existing is not None:
                return Response(
                    {
                        "detail": (
                            "Another student already uses this identifier. "
                            "Enrol the existing student instead."
                        ),
                        "code": "invalid",
                        "errors": {"school_identifier": ["Identifier already in use."]},
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        try:
            with transaction.atomic():
                student = Student.objects.create(
                    teacher=request.user,
                    display_name=data["display_name"],
                    school_identifier=identifier,
                    email=data.get("email", ""),
                )
                Enrollment.objects.create(classroom=classroom, student=student)
        except IntegrityError:
            return Response(
                {
                    "detail": "That student could not be added.",
                    "code": "conflict",
                    "errors": {},
                },
                status=status.HTTP_409_CONFLICT,
            )

        return Response(
            StudentSerializer(student, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="import-roster")
    def import_roster(self, request: Request, pk: str | None = None) -> Response:
        """Bulk roster import from a CSV file."""
        classroom = self.get_object()
        serializer = RosterImportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        upload = serializer.validated_data["file"]

        try:
            result = import_roster_csv(classroom=classroom, raw=upload.read())
        except RosterImportError as exc:
            return Response(
                {"detail": str(exc), "code": "invalid_csv", "errors": {}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(result.as_dict(), status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="topic-timeline")
    def topic_timeline(self, request: Request, pk: str | None = None) -> Response:
        classroom = self.get_object()
        return Response(build_topic_timeline(classroom))


class StudentViewSet(OwnedQuerysetMixin, viewsets.ModelViewSet):
    serializer_class = StudentSerializer
    queryset = Student.objects.all()

    def get_queryset(self):
        queryset = super().get_queryset()
        classroom_id = self.request.query_params.get("classroom")
        if classroom_id:
            queryset = queryset.filter(
                enrollments__classroom_id=classroom_id,
                enrollments__classroom__teacher=self.request.user,
            ).distinct()
        return queryset


class EnrollmentViewSet(OwnedQuerysetMixin, viewsets.ModelViewSet):
    serializer_class = EnrollmentSerializer
    queryset = Enrollment.objects.select_related("student", "classroom")
    owner_field = "classroom__teacher"

    def get_queryset(self):
        queryset = super().get_queryset()
        classroom_id = self.request.query_params.get("classroom")
        if classroom_id:
            queryset = queryset.filter(classroom_id=classroom_id)
        return queryset


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def roster_csv_template(request: Request) -> HttpResponse:
    """Downloads the sample roster CSV the import endpoint expects."""
    response = HttpResponse(SAMPLE_CSV, content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="caricue-roster-template.csv"'
    return response


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([PublicLookupThrottle])
def public_class_detail(request: Request, invite_token: str) -> Response:
    """Public class summary for the class QR join page."""
    classroom = get_object_or_404(
        Classroom.objects.select_related("teacher"),
        invite_token=invite_token,
        is_active=True,
    )
    return Response(
        {
            "name": classroom.name,
            "subject": classroom.subject,
            "level": classroom.level,
            "teacher_name": classroom.teacher.full_name,
            "self_enrollment_enabled": classroom.self_enrollment_enabled,
        }
    )


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([PublicJoinThrottle])
def public_class_join(request: Request, invite_token: str) -> Response:
    """Enrol a signed-in student via the class invite token."""
    account = get_student_account(request)
    if account is None:
        return Response(
            {
                "detail": "Sign in with your school Google account to join this class.",
                "code": "google_sign_in_required",
                "errors": {},
            },
            status=status.HTTP_401_UNAUTHORIZED,
        )

    classroom = get_object_or_404(
        Classroom.objects.select_related("teacher"),
        invite_token=invite_token,
        is_active=True,
    )
    try:
        result = join_class_via_invite(classroom=classroom, account=account)
    except ClassJoinError as exc:
        http_status = (
            status.HTTP_403_FORBIDDEN
            if exc.code == "enrollment_disabled"
            else status.HTTP_400_BAD_REQUEST
        )
        return Response(
            {"detail": exc.message, "code": exc.code, "errors": {}},
            status=http_status,
        )

    return Response(
        {
            "classroom_name": result.classroom_name,
            "student_id": result.student_id,
            "already_enrolled": result.already_enrolled,
        },
        status=status.HTTP_200_OK if result.already_enrolled else status.HTTP_201_CREATED,
    )
