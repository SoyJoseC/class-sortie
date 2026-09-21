"""CariCue REST API routes.

Everything under `/api/`. Two zones:

``/api/public/...``
    Unauthenticated, student-facing, throttled, validated. These are the only
    routes reachable without a teacher session.

everything else
    Requires a teacher session (DRF's default permission is
    `IsAuthenticated`) and is scoped to the owning teacher by
    `OwnedQuerysetMixin`.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from caricue.accounts import views as account_views
from caricue.activities import views as activity_views
from caricue.classroom import views as classroom_views
from caricue.core import views as core_views
from caricue.live import views as live_views

router = DefaultRouter()
router.register("classrooms", classroom_views.ClassroomViewSet, basename="classroom")
router.register("students", classroom_views.StudentViewSet, basename="student")
router.register("enrollments", classroom_views.EnrollmentViewSet, basename="enrollment")
router.register("activities", activity_views.ActivityViewSet, basename="activity")
router.register("questions", activity_views.QuestionViewSet, basename="question")
router.register("choices", activity_views.ChoiceViewSet, basename="choice")
router.register("sessions", live_views.LiveSessionViewSet, basename="livesession")
router.register("reflections", live_views.TeacherReflectionViewSet, basename="reflection")

auth_patterns = [
    path("csrf/", account_views.csrf, name="auth-csrf"),
    path("register/", account_views.RegisterView.as_view(), name="auth-register"),
    path("login/", account_views.LoginView.as_view(), name="auth-login"),
    path("logout/", account_views.LogoutView.as_view(), name="auth-logout"),
    path("me/", account_views.CurrentTeacherView.as_view(), name="auth-me"),
]

public_patterns = [
    path("sessions/lookup/", live_views.public_code_lookup, name="public-code-lookup"),
    path(
        "sessions/<str:public_token>/",
        live_views.PublicSessionView.as_view(),
        name="public-session",
    ),
    path(
        "sessions/<str:public_token>/join/",
        live_views.PublicJoinView.as_view(),
        name="public-join",
    ),
    path(
        "sessions/<str:public_token>/submit/",
        live_views.PublicSubmitView.as_view(),
        name="public-submit",
    ),
]

urlpatterns = [
    path("health/", core_views.health, name="health"),
    path("config/", core_views.client_config, name="client-config"),
    path("auth/", include(auth_patterns)),
    path("public/", include(public_patterns)),
    path("overview/", live_views.TeacherOverviewView.as_view(), name="teacher-overview"),
    path(
        "roster-template.csv",
        classroom_views.roster_csv_template,
        name="roster-csv-template",
    ),
    path("", include(router.urls)),
]
