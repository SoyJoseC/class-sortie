"""Classes, students and enrolments.

Privacy note: `Student` intentionally stores the smallest useful set of
fields. A display name is required (the teacher needs to recognise the row);
school identifier and email are optional and only exist to support roster
import and roster-based session identity.
"""

from __future__ import annotations

import secrets

from django.conf import settings
from django.db import models
from django.db.models.functions import Lower

from caricue.core.models import TimeStampedModel


def generate_invite_token() -> str:
    return secrets.token_hex(16)


class Classroom(TimeStampedModel):
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="classrooms",
    )
    name = models.CharField(max_length=120)
    subject = models.CharField(max_length=120, blank=True)
    level = models.CharField(
        max_length=60,
        blank=True,
        help_text="Grade, form or year level.",
    )
    academic_period = models.CharField(
        max_length=60,
        blank=True,
        help_text='Term or semester label, e.g. "2026 Term 1".',
    )
    is_active = models.BooleanField(default=True)
    invite_token = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        default=generate_invite_token,
    )
    self_enrollment_enabled = models.BooleanField(
        default=False,
        help_text="When enabled, students may join via the class QR with Google sign-in.",
    )

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                "teacher",
                Lower("name"),
                name="uniq_classroom_name_per_teacher",
            ),
        ]

    def __str__(self) -> str:
        return self.name

    @property
    def class_join_url(self) -> str:
        base = settings.PUBLIC_BASE_URL.rstrip("/")
        return f"{base}/join/class/{self.invite_token}"

    @property
    def roster_size(self) -> int:
        """Active enrolments; the denominator for completion rate."""
        return self.enrollments.filter(is_active=True).count()


class Student(TimeStampedModel):
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="students",
    )
    display_name = models.CharField(max_length=120)
    school_identifier = models.CharField(
        max_length=60,
        blank=True,
        help_text="Optional school/roll identifier used for roster-coded joins.",
    )
    email = models.EmailField(max_length=254, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["display_name"]
        constraints = [
            # Roster identifiers must be unique per teacher when provided, so
            # a coded join resolves to exactly one student.
            models.UniqueConstraint(
                "teacher",
                Lower("school_identifier"),
                condition=~models.Q(school_identifier=""),
                name="uniq_student_school_identifier_per_teacher",
            ),
        ]

    def __str__(self) -> str:
        return self.display_name


class Enrollment(TimeStampedModel):
    classroom = models.ForeignKey(
        Classroom,
        on_delete=models.CASCADE,
        related_name="enrollments",
    )
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="enrollments",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["student__display_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["classroom", "student"],
                name="uniq_enrollment_per_classroom_student",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.student.display_name} in {self.classroom.name}"

    @property
    def owner_teacher_id(self) -> int | None:
        return self.classroom.teacher_id
