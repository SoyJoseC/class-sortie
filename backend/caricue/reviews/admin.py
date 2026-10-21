from django.contrib import admin

from .models import ReviewEvent, ReviewItem


@admin.register(ReviewItem)
class ReviewItemAdmin(admin.ModelAdmin):
    list_display = ("topic_label", "classroom", "box", "last_score", "due_at")
    list_filter = ("box",)
    search_fields = ("topic_label", "topic_key")


@admin.register(ReviewEvent)
class ReviewEventAdmin(admin.ModelAdmin):
    list_display = ("review_item", "reason", "from_box", "to_box", "score", "created_at")
    list_filter = ("reason",)
