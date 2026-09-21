from django.contrib import admin

from .models import Activity, Choice, Question


class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 0


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 0
    show_change_link = True


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ["title", "teacher", "classroom", "status", "created_at"]
    list_filter = ["status"]
    search_fields = ["title", "topic"]
    autocomplete_fields = ["teacher", "classroom"]
    inlines = [QuestionInline]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ["activity", "position", "question_type", "is_required"]
    list_filter = ["question_type", "is_required"]
    search_fields = ["prompt"]
    inlines = [ChoiceInline]
