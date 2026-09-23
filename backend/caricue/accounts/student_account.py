"""Session helpers for authenticated students (separate from teachers)."""

from __future__ import annotations

from django.http import HttpRequest

from .models import StudentAccount

STUDENT_SESSION_KEY = "student_account_id"


def get_student_account(request: HttpRequest) -> StudentAccount | None:
    account_id = request.session.get(STUDENT_SESSION_KEY)
    if not account_id:
        return None
    return StudentAccount.objects.filter(pk=account_id).first()


def login_student(request: HttpRequest, account: StudentAccount) -> None:
    request.session[STUDENT_SESSION_KEY] = account.pk
    request.session.modified = True


def logout_student(request: HttpRequest) -> None:
    request.session.pop(STUDENT_SESSION_KEY, None)
    request.session.modified = True
