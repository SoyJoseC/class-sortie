"""Shared fixtures.

The factory fixtures build the smallest object graph each test needs rather
than one large shared fixture, so a failing test points at a single concern.
"""

from __future__ import annotations

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from caricue.accounts.models import Teacher
from caricue.activities.models import (
    Activity,
    ActivityStatus,
    Choice,
    Question,
    QuestionType,
)
from caricue.classroom.models import Classroom, Enrollment, Student
from caricue.live.services import launch_session

PASSWORD = "TestPassphrase123"


@pytest.fixture(autouse=True)
def _clear_throttle_cache():
    """Throttles are cache-backed; a leftover counter would leak between tests."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def api() -> APIClient:
    return APIClient()


@pytest.fixture
def make_teacher(db):
    counter = {"n": 0}

    def _make(email: str | None = None, **extra) -> Teacher:
        counter["n"] += 1
        return Teacher.objects.create_user(
            email=email or f"teacher{counter['n']}@example.edu",
            password=extra.pop("password", PASSWORD),
            full_name=extra.pop("full_name", f"Teacher {counter['n']}"),
            **extra,
        )

    return _make


@pytest.fixture
def teacher(make_teacher) -> Teacher:
    return make_teacher("owner@example.edu")


@pytest.fixture
def other_teacher(make_teacher) -> Teacher:
    return make_teacher("intruder@example.edu")


@pytest.fixture
def auth_client(api, teacher) -> APIClient:
    api.force_authenticate(user=teacher)
    return api


@pytest.fixture
def other_client(other_teacher) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=other_teacher)
    return client


@pytest.fixture
def make_classroom(db):
    def _make(teacher, name: str = "Form 4 IT", **extra) -> Classroom:
        return Classroom.objects.create(
            teacher=teacher,
            name=name,
            subject=extra.pop("subject", "Information Technology"),
            level=extra.pop("level", "Form 4"),
            academic_period=extra.pop("academic_period", "2026 Term 1"),
            **extra,
        )

    return _make


@pytest.fixture
def classroom(make_classroom, teacher) -> Classroom:
    return make_classroom(teacher)


@pytest.fixture
def make_student(db):
    def _make(teacher, display_name: str, identifier: str = "", **extra) -> Student:
        return Student.objects.create(
            teacher=teacher,
            display_name=display_name,
            school_identifier=identifier,
            **extra,
        )

    return _make


@pytest.fixture
def enrolled_students(make_student, teacher, classroom) -> list[Student]:
    students = []
    for index in range(1, 5):
        student = make_student(teacher, f"Student {index}", f"STU-00{index}")
        Enrollment.objects.create(classroom=classroom, student=student)
        students.append(student)
    return students


@pytest.fixture
def make_activity(db):
    def _make(teacher, classroom, *, with_questions: bool = True, **extra) -> Activity:
        activity = Activity.objects.create(
            teacher=teacher,
            classroom=classroom,
            title=extra.pop("title", "Hardware check"),
            topic=extra.pop("topic", "Storage and networking devices"),
            status=extra.pop("status", ActivityStatus.DRAFT),
            **extra,
        )
        if with_questions:
            mcq = Question.objects.create(
                activity=activity,
                position=1,
                prompt="Which component keeps data without power?",
                question_type=QuestionType.MULTIPLE_CHOICE,
                collect_confidence=True,
            )
            Choice.objects.create(
                question=mcq, text="Solid-state drive", is_correct=True, position=1
            )
            Choice.objects.create(question=mcq, text="RAM", is_correct=False, position=2)
            Choice.objects.create(
                question=mcq, text="CPU cache", is_correct=False, position=3
            )

            Question.objects.create(
                activity=activity,
                position=2,
                prompt="What does RAM stand for?",
                question_type=QuestionType.SHORT_TEXT,
                accepted_answers=["Random Access Memory"],
            )
            Question.objects.create(
                activity=activity,
                position=3,
                prompt="Explain the difference between a switch and a router.",
                question_type=QuestionType.SHORT_TEXT,
                is_required=False,
                accepted_answers=[],
            )
            Question.objects.create(
                activity=activity,
                position=4,
                prompt="How confident are you overall?",
                question_type=QuestionType.CONFIDENCE,
            )
        return activity

    return _make


@pytest.fixture
def activity(make_activity, teacher, classroom) -> Activity:
    return make_activity(teacher, classroom)


@pytest.fixture
def open_session(activity, enrolled_students):
    session, error = launch_session(activity=activity)
    assert error == ""
    return session


@pytest.fixture
def roster_session(activity, enrolled_students):
    session, error = launch_session(activity=activity, identity_mode="roster_identifier")
    assert error == ""
    return session


@pytest.fixture
def answers_for(db):
    """Builds a valid, complete answer payload for an activity."""

    def _build(
        activity, *, correct: bool = True, confidence: int | None = 4
    ) -> list[dict]:
        payload = []
        for question in activity.questions.prefetch_related("choices").order_by(
            "position"
        ):
            if question.question_type == QuestionType.MULTIPLE_CHOICE:
                choice = question.choices.filter(is_correct=correct).first()
                if choice is None:
                    choice = question.choices.first()
                answer = {"question": question.pk, "selected_choice": choice.pk}
                if question.collect_confidence and confidence is not None:
                    answer["confidence_value"] = confidence
                payload.append(answer)
            elif question.question_type == QuestionType.SHORT_TEXT:
                if question.normalized_accepted_answers():
                    text = "Random Access Memory" if correct else "Read Access Memory"
                else:
                    text = "A switch is local, a router joins networks."
                payload.append({"question": question.pk, "text_response": text})
            elif question.question_type == QuestionType.CONFIDENCE:
                payload.append(
                    {"question": question.pk, "confidence_value": confidence or 3}
                )
        return payload

    return _build
