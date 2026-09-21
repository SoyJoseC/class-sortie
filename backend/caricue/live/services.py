"""Domain services for launching sessions and accepting student submissions.

All the rules that must hold regardless of which endpoint is calling live
here, so the public API, the demo-data command and the tests exercise the same
code path.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from django.db import IntegrityError, transaction
from django.utils import timezone

from caricue.activities.models import (
    CONFIDENCE_MAX,
    CONFIDENCE_MIN,
    Activity,
    ActivityStatus,
    Question,
    QuestionType,
    normalize_text_answer,
)
from caricue.classroom.models import Student

from .models import (
    IdentityMode,
    LiveSession,
    Participant,
    Response,
    SessionStatus,
    allocate_unique_code,
    generate_public_token,
)

logger = logging.getLogger("caricue.live")


class SubmissionError(Exception):
    """A student-facing submission problem. The message is safe to display."""

    def __init__(self, message: str, code: str = "invalid") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


class SessionClosedError(SubmissionError):
    def __init__(self) -> None:
        super().__init__(
            "This session has been closed by your teacher.", "session_closed"
        )


class AlreadySubmittedError(SubmissionError):
    def __init__(self) -> None:
        super().__init__("You have already submitted your answers.", "already_submitted")


# --------------------------------------------------------------------------- #
# Launching and closing
# --------------------------------------------------------------------------- #
@transaction.atomic
def launch_session(
    *, activity: Activity, identity_mode: str | None = None
) -> tuple[LiveSession | None, str]:
    """Opens a live session for `activity`.

    Returns `(session, "")` on success or `(None, reason)` when the activity
    is not ready. Publishing the activity is part of launching, so a teacher
    never has to remember a separate "publish" step.
    """
    launchable, reason = activity.is_launchable()
    if not launchable:
        return None, reason

    mode = identity_mode or IdentityMode.DISPLAY_NAME
    if mode not in IdentityMode.values:
        return None, f"Unknown identity mode {mode!r}."

    if mode == IdentityMode.ROSTER_IDENTIFIER:
        has_identifiers = (
            Student.objects.filter(
                enrollments__classroom=activity.classroom,
                enrollments__is_active=True,
                is_active=True,
            )
            .exclude(school_identifier="")
            .exists()
        )
        if not has_identifiers:
            return None, (
                "No students in this class have a roster identifier. Add "
                "identifiers or launch with display-name join."
            )

    if activity.status != ActivityStatus.PUBLISHED:
        activity.status = ActivityStatus.PUBLISHED
        activity.save(update_fields=["status", "updated_at"])

    session = LiveSession.objects.create(
        activity=activity,
        classroom=activity.classroom,
        code=allocate_unique_code(),
        public_token=generate_public_token(),
        identity_mode=mode,
        status=SessionStatus.OPEN,
        started_at=timezone.now(),
    )
    logger.info("Opened session %s for activity %s", session.code, activity.pk)
    return session, ""


def close_session(session: LiveSession) -> LiveSession:
    session.close()
    logger.info("Closed session %s", session.code)
    return session


# --------------------------------------------------------------------------- #
# Joining
# --------------------------------------------------------------------------- #
@dataclass
class JoinResult:
    participant: Participant
    resumed: bool


@transaction.atomic
def join_session(*, session: LiveSession, identifier: str) -> JoinResult:
    """Creates (or resumes) a participant for an open session.

    `identifier` is a self-chosen display name or a roster identifier
    depending on `session.identity_mode`. A participant who has not submitted
    yet can rejoin with the same identifier, which is what makes the flow
    survive a dropped connection on a phone.
    """
    if not session.is_open:
        raise SessionClosedError

    cleaned = " ".join((identifier or "").split())
    if not cleaned:
        raise SubmissionError("Please enter your name to join.", "identifier_required")
    if len(cleaned) > 80:
        raise SubmissionError("That name is too long (80 characters max).")

    if session.identity_mode == IdentityMode.ROSTER_IDENTIFIER:
        student = Student.objects.filter(
            teacher=session.activity.teacher,
            school_identifier__iexact=cleaned,
            is_active=True,
            enrollments__classroom=session.classroom,
            enrollments__is_active=True,
        ).first()
        if student is None:
            # Uniform message: a student cannot enumerate the roster by
            # probing identifiers, and no roster data is echoed back.
            raise SubmissionError(
                "That identifier is not on this class list. Check with your teacher.",
                "identifier_not_recognised",
            )
        existing = Participant.objects.filter(
            live_session=session, student=student
        ).first()
        if existing is not None:
            if existing.has_submitted:
                raise AlreadySubmittedError
            return JoinResult(participant=existing, resumed=True)
        participant = Participant.objects.create(
            live_session=session, student=student, display_name=cleaned
        )
        return JoinResult(participant=participant, resumed=False)

    existing = Participant.objects.filter(
        live_session=session, student__isnull=True, display_name__iexact=cleaned
    ).first()
    if existing is not None:
        if existing.has_submitted:
            raise AlreadySubmittedError
        return JoinResult(participant=existing, resumed=True)

    try:
        participant = Participant.objects.create(
            live_session=session, display_name=cleaned
        )
    except IntegrityError as exc:  # concurrent join with the same name
        raise SubmissionError(
            "Someone just joined with that name. Please add an initial.",
            "name_taken",
        ) from exc
    return JoinResult(participant=participant, resumed=False)


# --------------------------------------------------------------------------- #
# Deterministic scoring
# --------------------------------------------------------------------------- #
def score_answer(
    *, question: Question, selected_choice_id: int | None, text_response: str
) -> bool | None:
    """Correctness for one answer, or None when not deterministically scorable.

    Multiple choice compares against the choices the teacher marked correct.
    Short text compares normalised strings against the teacher's accepted
    answers, and returns None when no accepted answers were supplied (the
    teacher will read those responses themselves). Confidence items are never
    right or wrong.
    """
    if question.question_type == QuestionType.MULTIPLE_CHOICE:
        if selected_choice_id is None:
            return False
        return question.choices.filter(pk=selected_choice_id, is_correct=True).exists()

    if question.question_type == QuestionType.SHORT_TEXT:
        accepted = question.normalized_accepted_answers()
        if not accepted:
            return None
        return normalize_text_answer(text_response) in accepted

    return None


# --------------------------------------------------------------------------- #
# Submitting
# --------------------------------------------------------------------------- #
@transaction.atomic
def submit_responses(
    *, session: LiveSession, participant: Participant, answers: list[dict]
) -> Participant:
    """Records a participant's whole submission, exactly once.

    Raises `SubmissionError` subclasses for every rejection a student could
    legitimately hit. The unique constraint on `(participant, question)` plus
    the `select_for_update` on the participant row make double submission
    impossible even with two devices racing.
    """
    if not session.is_open:
        raise SessionClosedError

    locked = (
        Participant.objects.select_for_update()
        .filter(pk=participant.pk)
        .select_related("live_session")
        .first()
    )
    if locked is None:
        raise SubmissionError("Please rejoin the session.", "participant_missing")
    if locked.has_submitted:
        raise AlreadySubmittedError

    questions = {
        question.pk: question
        for question in session.activity.questions.prefetch_related("choices")
    }
    if not questions:
        raise SubmissionError("This activity has no questions yet.", "no_questions")

    by_question = _index_answers(answers, questions)

    for question in questions.values():
        answer = by_question.get(question.pk)
        if question.is_required and not _is_answered(question, answer):
            raise SubmissionError(
                f"Question {question.position} needs an answer.",
                "required_answer_missing",
            )

    rows: list[Response] = []
    for question in questions.values():
        answer = by_question.get(question.pk)
        if answer is None:
            continue
        if not _is_answered(question, answer):
            continue  # optional and left blank

        selected_choice_id = answer.get("selected_choice")
        text_response = (answer.get("text_response") or "").strip()
        confidence = answer.get("confidence_value")

        if question.question_type == QuestionType.CONFIDENCE:
            # The scale value is the answer for a standalone confidence item.
            confidence = confidence if confidence is not None else answer.get("value")
            text_response = ""
            selected_choice_id = None

        rows.append(
            Response(
                participant=locked,
                question=question,
                selected_choice_id=selected_choice_id,
                text_response=text_response[:1000],
                confidence_value=confidence,
                is_correct=score_answer(
                    question=question,
                    selected_choice_id=selected_choice_id,
                    text_response=text_response,
                ),
            )
        )

    try:
        Response.objects.bulk_create(rows)
    except IntegrityError as exc:
        raise AlreadySubmittedError from exc

    locked.submitted_at = timezone.now()
    locked.save(update_fields=["submitted_at", "updated_at"])
    logger.info(
        "Recorded %d responses for participant %s in session %s",
        len(rows),
        locked.pk,
        session.code,
    )
    return locked


def _index_answers(
    answers: list[dict], questions: dict[int, Question]
) -> dict[int, dict]:
    """Validates the answer envelope and keys it by question id."""
    if not isinstance(answers, list):
        raise SubmissionError("Answers must be a list.")

    indexed: dict[int, dict] = {}
    for raw in answers:
        if not isinstance(raw, dict):
            raise SubmissionError("Each answer must be an object.")
        try:
            question_id = int(raw.get("question"))
        except (TypeError, ValueError) as exc:
            raise SubmissionError("Each answer needs a question id.") from exc

        question = questions.get(question_id)
        if question is None:
            raise SubmissionError("An answer referenced an unknown question.")
        if question_id in indexed:
            raise SubmissionError("Two answers were sent for the same question.")

        indexed[question_id] = _clean_answer(question, raw)
    return indexed


def _clean_answer(question: Question, raw: dict) -> dict:
    cleaned: dict = {}

    choice_id = raw.get("selected_choice")
    if choice_id not in (None, ""):
        if question.question_type != QuestionType.MULTIPLE_CHOICE:
            raise SubmissionError(f"Question {question.position} does not take a choice.")
        try:
            choice_id = int(choice_id)
        except (TypeError, ValueError) as exc:
            raise SubmissionError("Invalid choice.") from exc
        # The choice must belong to this question, so a student cannot submit
        # a choice id harvested from another activity.
        if not question.choices.filter(pk=choice_id).exists():
            raise SubmissionError(
                f"Invalid choice for question {question.position}.",
                "invalid_choice",
            )
        cleaned["selected_choice"] = choice_id

    text = raw.get("text_response")
    if text not in (None, ""):
        if question.question_type != QuestionType.SHORT_TEXT:
            raise SubmissionError(
                f"Question {question.position} does not take a text answer."
            )
        if not isinstance(text, str):
            raise SubmissionError("Text answers must be text.")
        if len(text) > 1000:
            raise SubmissionError(
                f"Answer to question {question.position} is too long "
                "(1000 characters max)."
            )
        cleaned["text_response"] = text

    confidence = raw.get("confidence_value", raw.get("value"))
    if confidence not in (None, ""):
        if (
            question.question_type != QuestionType.CONFIDENCE
            and not question.collect_confidence
        ):
            raise SubmissionError(
                f"Question {question.position} does not collect confidence."
            )
        try:
            confidence = int(confidence)
        except (TypeError, ValueError) as exc:
            raise SubmissionError("Confidence must be a whole number.") from exc
        if not CONFIDENCE_MIN <= confidence <= CONFIDENCE_MAX:
            raise SubmissionError(
                f"Confidence must be between {CONFIDENCE_MIN} and {CONFIDENCE_MAX}."
            )
        cleaned["confidence_value"] = confidence

    return cleaned


def _is_answered(question: Question, answer: dict | None) -> bool:
    if not answer:
        return False
    if question.question_type == QuestionType.MULTIPLE_CHOICE:
        return answer.get("selected_choice") is not None
    if question.question_type == QuestionType.SHORT_TEXT:
        return bool((answer.get("text_response") or "").strip())
    if question.question_type == QuestionType.CONFIDENCE:
        return answer.get("confidence_value") is not None
    return False
