"""Self-enrollment into a class via invite token and Google profile."""

from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction

from caricue.accounts.models import StudentAccount

from .models import Classroom, Enrollment, Student


class ClassJoinError(Exception):
    def __init__(self, message: str, code: str = "invalid") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


@dataclass
class ClassJoinResult:
    classroom_name: str
    student_id: int
    already_enrolled: bool


@transaction.atomic
def join_class_via_invite(
    *, classroom: Classroom, account: StudentAccount
) -> ClassJoinResult:
    if not classroom.self_enrollment_enabled:
        raise ClassJoinError(
            "This class is not accepting self-enrollment.", "enrollment_disabled"
        )

    student = Student.objects.filter(
        teacher=classroom.teacher,
        email__iexact=account.email,
    ).first()

    if student is None:
        student = Student.objects.create(
            teacher=classroom.teacher,
            display_name=account.full_name,
            email=account.email,
        )
    elif not student.display_name.strip():
        student.display_name = account.full_name
        student.save(update_fields=["display_name", "updated_at"])

    enrollment, created = Enrollment.objects.get_or_create(
        classroom=classroom,
        student=student,
        defaults={"is_active": True},
    )
    if not created and not enrollment.is_active:
        enrollment.is_active = True
        enrollment.save(update_fields=["is_active", "updated_at"])

    return ClassJoinResult(
        classroom_name=classroom.name,
        student_id=student.pk,
        already_enrolled=not created,
    )
