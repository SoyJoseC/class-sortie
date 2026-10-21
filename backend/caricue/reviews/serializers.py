from rest_framework import serializers

from .models import ReviewItem


class ReviewItemSerializer(serializers.ModelSerializer):
    classroom_name = serializers.CharField(source="classroom.name", read_only=True)
    last_session_code = serializers.SerializerMethodField()
    is_due = serializers.SerializerMethodField()
    interval_days = serializers.SerializerMethodField()

    class Meta:
        model = ReviewItem
        fields = [
            "id",
            "classroom",
            "classroom_name",
            "topic_key",
            "topic_label",
            "box",
            "last_score",
            "last_session",
            "last_session_code",
            "due_at",
            "snoozed_until",
            "is_due",
            "interval_days",
            "updated_at",
        ]
        read_only_fields = fields

    def get_last_session_code(self, item: ReviewItem) -> str | None:
        return item.last_session.code if item.last_session_id else None

    def get_is_due(self, item: ReviewItem) -> bool:
        return item.is_due()

    def get_interval_days(self, item: ReviewItem) -> int:
        from .schedule import interval_for_box

        return interval_for_box(item.box)


class SnoozeSerializer(serializers.Serializer):
    days = serializers.IntegerField(min_value=1, max_value=60, default=1)
