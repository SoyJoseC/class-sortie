from __future__ import annotations

from django.contrib.auth import login, logout
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.debug import sensitive_post_parameters
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from caricue.core.throttling import AuthAttemptThrottle

from .serializers import LoginSerializer, RegisterSerializer, TeacherSerializer


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
