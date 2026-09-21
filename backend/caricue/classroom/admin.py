from django.contrib import admin

from .models import Classroom, Enrollment, Student


@admin.register(Classroom)
class ClassroomAdmin(admin.ModelAdmin):
    list_display = ["name", "teacher", "subject", "level", "academic_period", "is_active"]
    list_filter = ["is_active", "academic_period"]
    search_fields = ["name", "subject", "teacher__email"]
    autocomplete_fields = ["teacher"]


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ["display_name", "school_identifier", "teacher", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["display_name", "school_identifier"]
    autocomplete_fields = ["teacher"]


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ["student", "classroom", "is_active"]
    list_filter = ["is_active"]
    autocomplete_fields = ["classroom", "student"]
