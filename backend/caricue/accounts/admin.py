from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Teacher


@admin.register(Teacher)
class TeacherAdmin(UserAdmin):
    ordering = ["email"]
    list_display = ["email", "full_name", "school_name", "is_active", "is_staff"]
    search_fields = ["email", "full_name", "school_name"]
    list_filter = ["is_active", "is_staff", "is_superuser"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profile", {"fields": ("full_name", "school_name")}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "full_name", "password1", "password2"),
            },
        ),
    )
