from __future__ import annotations

import urllib.parse

from django.contrib.auth import login, logout
from django.http import HttpResponseRedirect
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.debug import sensitive_post_parameters
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from caricue.core.throttling import AuthAttemptThrottle

from .google_oauth import (
    GoogleOAuthError,
    build_authorization_url,
    email_domain_allowed,
    exchange_code,
    new_oauth_state,
)
from .models import StudentAccount, Teacher
from .serializers import LoginSerializer, RegisterSerializer, TeacherSerializer
from .student_account import get_student_account, login_student, logout_student


@api_view(["GET"])
@permission_classes([AllowAny])
@ensure_csrf_cookie
def csrf(request: Request) -> Response:
    """Sets the CSRF cookie and returns the token.

    The SPA calls this once on boot so unsafe requests can send X-CSRFToken.
    """
    return Response({"csrf_token": get_token(request)})


# `sensitive_post_parameters` needs the raw HttpRequest, which is only what
# `dispatch` sees; by the time `post` runs, DRF has wrapped it in its own
# Request. Decorating dispatch keeps the password out of error reports.
@method_decorator(sensitive_post_parameters("password"), name="dispatch")
class RegisterView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AuthAttemptThrottle]

    def post(self, request: Request) -> Response:
        serializer = RegisterSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        teacher = serializer.save()
        login(request, teacher)
        return Response(TeacherSerializer(teacher).data, status=status.HTTP_201_CREATED)


@method_decorator(sensitive_post_parameters("password"), name="dispatch")
class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AuthAttemptThrottle]

    def post(self, request: Request) -> Response:
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        teacher = serializer.validated_data["teacher"]
        # Rotates the session key, so a pre-login fixation attempt is void.
        login(request, teacher)
        return Response(TeacherSerializer(teacher).data)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CurrentTeacherView(RetrieveUpdateAPIView):
    """`GET`/`PATCH` the signed-in teacher's own profile."""

    serializer_class = TeacherSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        return self.request.user


def _safe_next_url(next_url: str | None, default: str) -> str:
    if not next_url or not next_url.startswith("/") or next_url.startswith("//"):
        return default
    return next_url


@api_view(["GET"])
@permission_classes([AllowAny])
@throttle_classes([AuthAttemptThrottle])
def google_login(request: Request) -> HttpResponseRedirect:
    role = request.query_params.get("role", "teacher")
    if role not in {"teacher", "student"}:
        role = "teacher"
    default_next = "/app" if role == "teacher" else "/join"
    next_url = _safe_next_url(request.query_params.get("next"), default_next)
    state = new_oauth_state()
    request.session["oauth_state"] = state
    request.session["oauth_role"] = role
    request.session["oauth_next"] = next_url
    request.session.modified = True
    try:
        url = build_authorization_url(state=state)
    except GoogleOAuthError as exc:
        params = urllib.parse.urlencode({"oauth_error": exc.code})
        return HttpResponseRedirect(f"{default_next}?{params}")
    return HttpResponseRedirect(url)


@api_view(["GET"])
@permission_classes([AllowAny])
@throttle_classes([AuthAttemptThrottle])
def google_callback(request: Request) -> HttpResponseRedirect:
    default_next = "/login"
    stored_state = request.session.pop("oauth_state", None)
    role = request.session.pop("oauth_role", "teacher")
    next_url = _safe_next_url(request.session.pop("oauth_next", None), default_next)

    error = request.query_params.get("error")
    if error:
        params = urllib.parse.urlencode({"oauth_error": error})
        return HttpResponseRedirect(f"{next_url}?{params}")

    code = request.query_params.get("code")
    state = request.query_params.get("state")
    if not code or not state or state != stored_state:
        params = urllib.parse.urlencode({"oauth_error": "invalid_state"})
        return HttpResponseRedirect(f"{next_url}?{params}")

    try:
        profile = exchange_code(code)
    except GoogleOAuthError as exc:
        params = urllib.parse.urlencode({"oauth_error": exc.code})
        return HttpResponseRedirect(f"{next_url}?{params}")

    if not email_domain_allowed(profile.email):
        params = urllib.parse.urlencode({"oauth_error": "domain_not_allowed"})
        return HttpResponseRedirect(f"{next_url}?{params}")

    if role == "student":
        logout(request)
        account, _ = StudentAccount.objects.update_or_create(
            google_sub=profile.sub,
            defaults={"email": profile.email, "full_name": profile.full_name},
        )
        login_student(request, account)
        return HttpResponseRedirect(next_url)

    logout_student(request)
    teacher = Teacher.objects.filter(email__iexact=profile.email).first()
    if teacher is None:
        teacher = Teacher.objects.create(
            email=profile.email,
            full_name=profile.full_name,
            google_sub=profile.sub,
        )
        teacher.set_unusable_password()
        teacher.save(update_fields=["password"])
    else:
        if not teacher.google_sub:
            teacher.google_sub = profile.sub
            teacher.save(update_fields=["google_sub", "updated_at"])
    login(request, teacher, backend="django.contrib.auth.backends.ModelBackend")
    return HttpResponseRedirect(next_url)


@api_view(["GET"])
@permission_classes([AllowAny])
def student_me(request: Request) -> Response:
    account = get_student_account(request)
    if account is None:
        return Response(status=status.HTTP_401_UNAUTHORIZED)
    return Response(
        {"id": account.pk, "email": account.email, "full_name": account.full_name}
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def student_logout(request: Request) -> Response:
    logout_student(request)
    return Response(status=status.HTTP_204_NO_CONTENT)
