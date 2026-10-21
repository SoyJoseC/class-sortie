from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from caricue.core.permissions import OwnedQuerysetMixin

from .generator import create_review_activity
from .models import ReviewItem
from .schedule import due_queryset, snooze_review_item
from .serializers import ReviewItemSerializer, SnoozeSerializer


class ReviewItemViewSet(OwnedQuerysetMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = ReviewItemSerializer
    queryset = ReviewItem.objects.select_related("classroom", "last_session")
    owner_field = "classroom__teacher"

    @action(detail=True, methods=["post"], url_path="create-activity")
    def create_activity(self, request: Request, pk: str | None = None) -> Response:
        item = self.get_object()
        try:
            activity = create_review_activity(item, request.user)
        except ValueError as exc:
            return Response(
                {"detail": str(exc), "code": "invalid", "errors": {}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({"activity_id": activity.pk}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def snooze(self, request: Request, pk: str | None = None) -> Response:
        item = self.get_object()
        serializer = SnoozeSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        snooze_review_item(item, days=serializer.validated_data.get("days", 1))
        item.refresh_from_db()
        return Response(ReviewItemSerializer(item).data)


class DueReviewsView(APIView):
    """Every card that is due across the teacher's classes."""

    def get(self, request: Request) -> Response:
        items = due_queryset(
            ReviewItem.objects.filter(classroom__teacher=request.user).select_related(
                "classroom", "last_session"
            )
        )
        return Response(ReviewItemSerializer(items, many=True).data)
