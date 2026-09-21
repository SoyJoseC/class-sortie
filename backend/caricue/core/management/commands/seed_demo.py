"""Creates a self-contained demonstration dataset.

Everything here is fictional. No real student data is committed to this
repository, and the command refuses to run unless it is pointed at a database
you have explicitly opted in to seeding.

Produces:
  * one demo teacher
  * one IT class with a roster of fictional students
  * one activity on computer hardware and networking
  * one closed session with a realistic spread of responses and a reflection
  * one follow-up closed session (linked via follow_up_of_session) with improved scores
  * one open session, ready to demonstrate the QR / short-code workflow
"""

from __future__ import annotations

import random
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from caricue.accounts.models import Teacher
from caricue.activities.follow_up import create_follow_up_activity
from caricue.activities.models import (
    Activity,
    ActivityStatus,
    Choice,
    Question,
    QuestionType,
)
from caricue.classroom.models import Classroom, Enrollment, Student
from caricue.live.models import (
    IdentityMode,
    LiveSession,
    PlanImpact,
    TeacherReflection,
)
from caricue.live.services import join_session, launch_session, submit_responses

DEMO_EMAIL = "teacher@caricue.demo"
DEMO_PASSWORD = "CariCueDemo2026"  # noqa: S105 - documented demo credential

DEMO_STUDENTS = [
    ("Amara Joseph", "STU-001"),
    ("Devon Charles", "STU-002"),
    ("Keisha Boodram", "STU-003"),
    ("Rohan Persad", "STU-004"),
    ("Shanice Williams", "STU-005"),
    ("Tariq Mohammed", "STU-006"),
    ("Naomi Alleyne", "STU-007"),
    ("Kirk Sampson", "STU-008"),
    ("Anisa Khan", "STU-009"),
    ("Jerome Baptiste", "STU-010"),
]

ACTIVITY_QUESTIONS: list[dict[str, Any]] = [
    {
        "prompt": (
            "Which component stores data permanently, even when the computer "
            "is powered off?"
        ),
        "question_type": QuestionType.MULTIPLE_CHOICE,
        "collect_confidence": True,
        "choices": [
            ("RAM", False),
            ("Solid-state drive", True),
            ("CPU cache", False),
            ("GPU memory", False),
        ],
    },
    {
        "prompt": (
            "A device needs to send data to another network. Which device "
            "makes that routing decision?"
        ),
        "question_type": QuestionType.MULTIPLE_CHOICE,
        "collect_confidence": True,
        "choices": [
            ("Network switch", False),
            ("Router", True),
            ("Repeater", False),
            ("Network cable", False),
        ],
    },
    {
        "prompt": "What does RAM stand for?",
        "question_type": QuestionType.SHORT_TEXT,
        "collect_confidence": False,
        "accepted_answers": [
            "Random Access Memory",
            "random-access memory",
        ],
    },
    {
        "prompt": (
            "In your own words, what is the difference between a switch and a router?"
        ),
        "question_type": QuestionType.SHORT_TEXT,
        "is_required": False,
        "collect_confidence": False,
        # No accepted answers on purpose: this stays unscored and the teacher
        # reads the responses. It demonstrates that CariCue does not grade
        # open-ended writing.
        "accepted_answers": [],
    },
    {
        "prompt": "How confident do you feel about today's topic overall?",
        "question_type": QuestionType.CONFIDENCE,
    },
]

#: Fictional free-text answers for the unscored explanation question.
EXPLANATION_ANSWERS = [
    "A switch connects computers in the same network, "
    "a router connects different networks.",
    "switch is for inside the network and router sends traffic outside",
    "A router finds the path between networks. A switch just forwards frames locally.",
    "They both connect devices but the router has the IP addresses",
    "not sure, i think a switch is faster",
    "switch = same network, router = between networks",
]

#: Short-text answers for "What does RAM stand for?" - a mix that exercises
#: normalisation (case, spacing) and genuine misconceptions.
RAM_ANSWERS = [
    "Random Access Memory",
    "random access memory",
    "  Random  Access Memory  ",
    "RANDOM ACCESS MEMORY",
    "Read Access Memory",
    "Rapid Access Memory",
    "Random Acess Memory",
]


class Command(BaseCommand):
    help = "Seeds a fictional demonstration dataset for CariCue."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete the existing demo teacher and all their data first.",
        )
        parser.add_argument(
            "--seed",
            type=int,
            default=20260908,
            help="Random seed, so demo response data is reproducible.",
        )

    @transaction.atomic
    def handle(self, *args, **options) -> None:
        if not settings.DEBUG and not options["reset"]:
            # A stray `seed_demo` against production would inject fake
            # students into a real teacher's dashboard.
            self.stdout.write(
                self.style.WARNING(
                    "DEBUG is off. Re-run with --reset if you really intend to "
                    "seed demo data into this database."
                )
            )
            raise CommandError("Refusing to seed demo data outside DEBUG.")

        rng = random.Random(options["seed"])

        if options["reset"]:
            deleted, _ = Teacher.objects.filter(email=DEMO_EMAIL).delete()
            if deleted:
                self.stdout.write(f"Removed existing demo data ({deleted} rows).")

        teacher, created = Teacher.objects.get_or_create(
            email=DEMO_EMAIL,
            defaults={
                "full_name": "Ms. Adanna Rowley",
                "school_name": "Northern Coast Secondary (demo)",
            },
        )
        if created:
            teacher.set_password(DEMO_PASSWORD)
            teacher.save(update_fields=["password"])
            self.stdout.write(self.style.SUCCESS(f"Created teacher {DEMO_EMAIL}"))
        else:
            self.stdout.write(f"Reusing existing teacher {DEMO_EMAIL}")

        classroom = self._seed_classroom(teacher)
        students = self._seed_roster(teacher, classroom)
        activity = self._seed_activity(teacher, classroom)

        closed_session = self._seed_completed_session(activity, students, rng)
        follow_up_session = self._seed_follow_up_session(
            activity, closed_session, teacher, students, rng
        )
        open_session = self._seed_open_session(activity)

        self._report(
            teacher, classroom, activity, closed_session, follow_up_session, open_session
        )

    # -- pieces ------------------------------------------------------------ #
    def _seed_classroom(self, teacher: Teacher) -> Classroom:
        classroom, created = Classroom.objects.get_or_create(
            teacher=teacher,
            name="Form 4 Information Technology",
            defaults={
                "subject": "Information Technology",
                "level": "Form 4",
                "academic_period": "2026 Term 1",
            },
        )
        self.stdout.write(
            f"{'Created' if created else 'Reusing'} class {classroom.name!r}"
        )
        return classroom

    def _seed_roster(self, teacher: Teacher, classroom: Classroom) -> list[Student]:
        students: list[Student] = []
        for display_name, identifier in DEMO_STUDENTS:
            student, _ = Student.objects.get_or_create(
                teacher=teacher,
                school_identifier=identifier,
                defaults={"display_name": display_name},
            )
            Enrollment.objects.get_or_create(classroom=classroom, student=student)
            students.append(student)
        self.stdout.write(f"Roster: {len(students)} students enrolled")
        return students

    def _seed_activity(self, teacher: Teacher, classroom: Classroom) -> Activity:
        activity, created = Activity.objects.get_or_create(
            teacher=teacher,
            classroom=classroom,
            title="Hardware and networking check",
            defaults={
                "topic": "Storage components and the role of switches vs routers",
                "status": ActivityStatus.PUBLISHED,
            },
        )
        if not created and activity.questions.exists():
            self.stdout.write("Reusing existing activity questions")
            return activity

        activity.questions.all().delete()
        for position, spec in enumerate(ACTIVITY_QUESTIONS, start=1):
            question = Question.objects.create(
                activity=activity,
                position=position,
                prompt=spec["prompt"],
                question_type=spec["question_type"],
                is_required=spec.get("is_required", True),
                collect_confidence=spec.get("collect_confidence", False),
                accepted_answers=spec.get("accepted_answers", []),
            )
            for choice_position, (text, is_correct) in enumerate(
                spec.get("choices", []), start=1
            ):
                Choice.objects.create(
                    question=question,
                    text=text,
                    is_correct=is_correct,
                    position=choice_position,
                )
        self.stdout.write(
            f"Activity {activity.title!r} with {activity.questions.count()} questions"
        )
        return activity

    def _seed_completed_session(
        self, activity: Activity, students: list[Student], rng: random.Random
    ) -> LiveSession:
        session, error = launch_session(
            activity=activity, identity_mode=IdentityMode.ROSTER_IDENTIFIER
        )
        if session is None:
            raise CommandError(f"Could not launch demo session: {error}")

        questions = list(activity.questions.prefetch_related("choices"))
        # 8 of 10 students submit, so completion rate is visibly below 100%.
        participating = students[:8]

        for index, student in enumerate(participating):
            result = join_session(session=session, identifier=student.school_identifier)
            answers = self._build_answers(questions, index, rng)
            submit_responses(
                session=session,
                participant=result.participant,
                answers=answers,
            )

        session.close()
        session.started_at = timezone.now() - timedelta(days=5)
        session.closed_at = timezone.now() - timedelta(days=4)
        session.save(update_fields=["started_at", "closed_at"])

        TeacherReflection.objects.get_or_create(
            live_session=session,
            defaults={
                "primary_gap": (
                    "Students confuse the roles of a switch and a router when "
                    "traffic leaves the local network."
                ),
                "plan_impact": PlanImpact.CHANGED,
                "planned_action": (
                    "Open next lesson with a 10-minute packet-journey diagram "
                    "on the board, then re-check with a two-question exit "
                    "ticket. Postpone the IP addressing worksheet by one day."
                ),
                "notes": (
                    "Three students were confidently wrong on question 2, so a "
                    "whole-class correction is needed rather than small-group "
                    "support."
                ),
            },
        )
        self.stdout.write(
            f"Completed session {session.code} with {len(participating)} submissions"
        )
        return session

    def _seed_follow_up_session(
        self,
        source_activity: Activity,
        baseline_session: LiveSession,
        teacher: Teacher,
        students: list[Student],
        rng: random.Random,
    ) -> LiveSession:
        """A follow-up check with improved scores to demo session comparison."""
        follow_up_activity = create_follow_up_activity(
            baseline_session, teacher, include_confidence=True
        )
        session, error = launch_session(
            activity=follow_up_activity, identity_mode=IdentityMode.ROSTER_IDENTIFIER
        )
        if session is None:
            raise CommandError(f"Could not launch follow-up session: {error}")

        questions = list(follow_up_activity.questions.prefetch_related("choices"))
        participating = students[:8]

        for index, student in enumerate(participating):
            # Stronger performance than the baseline session.
            base_strengths = [0.95, 0.9, 0.85, 0.8, 0.75, 0.7, 0.65, 0.6]
            strength = min(1.0, base_strengths[index % 8] + 0.2)
            result = join_session(session=session, identifier=student.school_identifier)
            answers = self._build_answers_with_strength(questions, strength, rng)
            submit_responses(
                session=session,
                participant=result.participant,
                answers=answers,
            )

        session.close()
        session.started_at = timezone.now() - timedelta(days=2)
        session.closed_at = timezone.now() - timedelta(days=1)
        session.save(update_fields=["started_at", "closed_at"])

        self.stdout.write(
            f"Follow-up session {session.code} with improved scores "
            f"(activity linked to {baseline_session.code})"
        )
        return session

    def _build_answers(
        self, questions: list[Question], index: int, rng: random.Random
    ) -> list[dict]:
        """Builds one student's answers with a deliberate performance spread."""
        # Roughly: strong students first, then mixed, then two who struggle.
        strength = [0.95, 0.9, 0.8, 0.7, 0.55, 0.5, 0.3, 0.25][index % 8]
        answers: list[dict] = []

        for question in questions:
            if question.question_type == QuestionType.MULTIPLE_CHOICE:
                choices = list(question.choices.all())
                correct = next(c for c in choices if c.is_correct)
                distractors = [c for c in choices if not c.is_correct]
                gets_it_right = rng.random() < strength
                chosen = correct if gets_it_right else rng.choice(distractors)

                answer = {"question": question.pk, "selected_choice": chosen.pk}
                if question.collect_confidence:
                    if gets_it_right:
                        answer["confidence_value"] = rng.choice([3, 4, 4, 5])
                    else:
                        # Some wrong answers come with high confidence: this is
                        # the signal the dashboard is built to surface.
                        answer["confidence_value"] = rng.choice([1, 2, 4, 5])
                answers.append(answer)

            elif question.question_type == QuestionType.SHORT_TEXT:
                if question.normalized_accepted_answers():
                    pool = RAM_ANSWERS[:4] if rng.random() < strength else RAM_ANSWERS[4:]
                    answers.append(
                        {"question": question.pk, "text_response": rng.choice(pool)}
                    )
                else:
                    answers.append(
                        {
                            "question": question.pk,
                            "text_response": rng.choice(EXPLANATION_ANSWERS),
                        }
                    )

            elif question.question_type == QuestionType.CONFIDENCE:
                level = max(1, min(5, round(strength * 5)))
                answers.append({"question": question.pk, "confidence_value": level})

        return answers

    def _build_answers_with_strength(
        self, questions: list[Question], strength: float, rng: random.Random
    ) -> list[dict]:
        """Like _build_answers but with an explicit strength factor."""
        answers: list[dict] = []
        for question in questions:
            if question.question_type == QuestionType.MULTIPLE_CHOICE:
                choices = list(question.choices.all())
                correct = next(c for c in choices if c.is_correct)
                distractors = [c for c in choices if not c.is_correct]
                gets_it_right = rng.random() < strength
                chosen = correct if gets_it_right else rng.choice(distractors)
                answer = {"question": question.pk, "selected_choice": chosen.pk}
                if question.collect_confidence:
                    answer["confidence_value"] = rng.choice([3, 4, 4, 5])
                answers.append(answer)
            elif question.question_type == QuestionType.SHORT_TEXT:
                if question.normalized_accepted_answers():
                    pool = RAM_ANSWERS[:4] if rng.random() < strength else RAM_ANSWERS[4:]
                    answers.append(
                        {"question": question.pk, "text_response": rng.choice(pool)}
                    )
                else:
                    answers.append(
                        {
                            "question": question.pk,
                            "text_response": rng.choice(EXPLANATION_ANSWERS),
                        }
                    )
            elif question.question_type == QuestionType.CONFIDENCE:
                level = max(1, min(5, round(strength * 5)))
                answers.append({"question": question.pk, "confidence_value": level})
        return answers

    def _seed_open_session(self, activity: Activity) -> LiveSession:
        existing = LiveSession.objects.filter(activity=activity, status="open").first()
        if existing is not None:
            self.stdout.write(f"Reusing open session {existing.code}")
            return existing

        session, error = launch_session(
            activity=activity, identity_mode=IdentityMode.DISPLAY_NAME
        )
        if session is None:
            raise CommandError(f"Could not open demo session: {error}")
        self.stdout.write(f"Open session {session.code} ready for the QR demo")
        return session

    def _report(
        self,
        teacher: Teacher,
        classroom: Classroom,
        activity: Activity,
        closed_session: LiveSession,
        follow_up_session: LiveSession,
        open_session: LiveSession,
    ) -> None:
        style = self.style
        self.stdout.write("")
        self.stdout.write(style.SUCCESS("=" * 66))
        self.stdout.write(style.SUCCESS(" CariCue demo data ready"))
        self.stdout.write(style.SUCCESS("=" * 66))
        self.stdout.write(f"  Teacher login : {teacher.email}")
        self.stdout.write(f"  Password      : {DEMO_PASSWORD}")
        self.stdout.write(f"  Class         : {classroom.name}")
        self.stdout.write(f"  Activity      : {activity.title}")
        self.stdout.write("")
        self.stdout.write("  Baseline session (results + reflection):")
        self.stdout.write(
            f"    code {closed_session.code}  status {closed_session.status}"
        )
        self.stdout.write("")
        self.stdout.write("  Follow-up session (comparison + improved scores):")
        self.stdout.write(
            f"    code {follow_up_session.code}  status {follow_up_session.status}"
        )
        self.stdout.write("")
        self.stdout.write("  Open session (student join / QR demo):")
        self.stdout.write(f"    code {open_session.code}")
        self.stdout.write(f"    url  {open_session.join_url}")
        self.stdout.write(style.SUCCESS("=" * 66))
        self.stdout.write(
            style.WARNING(
                "  All students and responses above are fictional. Do not use "
                "these credentials outside local development."
            )
        )
