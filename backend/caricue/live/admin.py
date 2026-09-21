from django.contrib import admin

from .models import LiveSession, Participant, Response, TeacherReflection


@admin.register(LiveSession)
class LiveSessionAdmin(admin.ModelAdmin):
    list_display = ["code", "activity", "classroom", "status", "started_at", "closed_at"]
    list_filter = ["status", "identity_mode"]
    search_fields = ["code"]
    readonly_fields = ["code", "public_token"]


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = ["__str__", "live_session", "student", "submitted_at"]
    list_filter = ["live_session__status"]
    readonly_fields = ["participant_token"]


@admin.register(Response)
class ResponseAdmin(admin.ModelAdmin):
    list_display = ["participant", "question", "is_correct", "confidence_value"]
    list_filter = ["is_correct", "confidence_value"]


@admin.register(TeacherReflection)
class TeacherReflectionAdmin(admin.ModelAdmin):
    list_display = ["live_session", "plan_impact", "created_at"]
    list_filter = ["plan_impact"]
    search_fields = ["primary_gap", "planned_action"]
