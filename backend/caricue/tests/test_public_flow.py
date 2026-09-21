"""The student journey: code lookup, session read, join, submit, confirmation.

These endpoints are unauthenticated, so each test also asserts what a student
device must *not* be able to see or do.
"""

from __future__ import annotations

import pytest
from django.urls import reverse

from caricue.live.models import Participant, Response

pytestmark = pytest.mark.django_db


def lookup_url() -> str:
    return reverse("public-code-lookup")


def session_url(token: str) -> str:
    return reverse("public-session", args=[token])


def join_url(token: str) -> str:
    return reverse("public-join", args=[token])


def submit_url(token: str) -> str:
    return reverse("public-submit", args=[token])


def join(api, session, identifier: str = "Amara J") -> str:
    response = api.post(
        join_url(session.public_token), {"identifier": identifier}, format="json"
    )
    assert response.status_code in (200, 201), response.data
    return response.data["participant_token"]


# --------------------------------------------------------------------------- #
# Short-code lookup
# --------------------------------------------------------------------------- #
def test_short_code_resolves_to_the_public_token(api, open_session):
    response = api.get(lookup_url(), {"code": open_session.code})
    assert response.status_code == 200
    assert response.data["public_token"] == open_session.public_token


def test_short_code_lookup_is_case_and_whitespace_tolerant(api, open_session):
    response = api.get(lookup_url(), {"code": f" {open_session.code.lower()} "})
    assert response.status_code == 200


def test_unknown_code_returns_a_safe_404(api):
    response = api.get(lookup_url(), {"code": "ZZZZZZ"})
    assert response.status_code == 404
    assert response.data["code"] == "session_not_found"


def test_closed_session_code_no_longer_resolves(api, auth_client, open_session):
    auth_client.post(reverse("livesession-close", args=[open_session.pk]))
    response = api.get(lookup_url(), {"code": open_session.code})
    assert response.status_code == 404


def test_lookup_rejects_non_alphanumeric_codes(api):
    response = api.get(lookup_url(), {"code": "../../etc"})
    assert response.status_code == 400


# --------------------------------------------------------------------------- #
# Public session read
# --------------------------------------------------------------------------- #
def test_public_session_exposes_questions_without_the_answer_key(api, open_session):
    response = api.get(session_url(open_session.public_token))

    assert response.status_code == 200
    assert response.data["is_open"] is True
    assert len(response.data["questions"]) == 4

    body = str(response.data)
    assert "is_correct" not in body
    assert "accepted_answers" not in body


def test_public_session_does_not_expose_the_roster_or_teacher(
    api, open_session, enrolled_students
):
    response = api.get(session_url(open_session.public_token))
    body = str(response.data)

    for student in enrolled_students:
        assert student.display_name not in body
        assert student.school_identifier not in body
    assert "teacher" not in response.data
    assert open_session.activity.teacher.email not in body


def test_unknown_token_returns_404(api):
    response = api.get(session_url("0" * 32))
    assert response.status_code == 404


def test_closed_session_is_described_but_withholds_questions(
    api, auth_client, open_session
):
    auth_client.post(reverse("livesession-close", args=[open_session.pk]))
    response = api.get(session_url(open_session.public_token))

    assert response.status_code == 200
    assert response.data["is_open"] is False
    assert response.data["questions"] == []


# --------------------------------------------------------------------------- #
# Joining
# --------------------------------------------------------------------------- #
def test_join_with_a_display_name_creates_a_participant(api, open_session):
    response = api.post(
        join_url(open_session.public_token), {"identifier": "Amara J"}, format="json"
    )
    assert response.status_code == 201
    assert response.data["display_label"] == "Amara J"
    assert response.data["participant_token"]
    assert Participant.objects.filter(live_session=open_session).count() == 1


def test_join_requires_a_non_blank_identifier(api, open_session):
    response = api.post(
        join_url(open_session.public_token), {"identifier": "   "}, format="json"
    )
    assert response.status_code == 400


def test_rejoining_before_submitting_resumes_the_same_participant(api, open_session):
    first = api.post(
        join_url(open_session.public_token), {"identifier": "Amara J"}, format="json"
    )
    second = api.post(
        join_url(open_session.public_token), {"identifier": "amara j"}, format="json"
    )

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.data["resumed"] is True
    assert second.data["participant_token"] == first.data["participant_token"]
    assert Participant.objects.filter(live_session=open_session).count() == 1


def test_join_in_roster_mode_matches_the_school_identifier(
    api, roster_session, enrolled_students
):
    student = enrolled_students[0]
    response = api.post(
        join_url(roster_session.public_token),
        {"identifier": student.school_identifier.lower()},
        format="json",
    )
    assert response.status_code == 201
    assert response.data["display_label"] == student.display_name

    participant = Participant.objects.get(live_session=roster_session)
    assert participant.student == student


def test_unknown_roster_identifier_is_rejected_without_leaking_the_roster(
    api, roster_session, enrolled_students
):
    response = api.post(
        join_url(roster_session.public_token),
        {"identifier": "STU-999"},
        format="json",
    )
    assert response.status_code == 400
    assert response.data["code"] == "identifier_not_recognised"
    for student in enrolled_students:
        assert student.display_name not in str(response.data)


def test_a_student_from_another_class_cannot_join(
    api, roster_session, make_student, teacher
):
    outsider = make_student(teacher, "Other Class", "OTH-001")
    response = api.post(
        join_url(roster_session.public_token),
        {"identifier": outsider.school_identifier},
        format="json",
    )
    assert response.status_code == 400


def test_cannot_join_a_closed_session(api, auth_client, open_session):
    auth_client.post(reverse("livesession-close", args=[open_session.pk]))
    response = api.post(
        join_url(open_session.public_token), {"identifier": "Late Arrival"}, format="json"
    )
    assert response.status_code == 409
    assert response.data["code"] == "session_closed"


# --------------------------------------------------------------------------- #
# Submitting
# --------------------------------------------------------------------------- #
def test_submit_records_responses_and_confirms(api, open_session, activity, answers_for):
    token = join(api, open_session)
    response = api.post(
        submit_url(open_session.public_token),
        {"participant_token": token, "answers": answers_for(activity)},
        format="json",
    )

    assert response.status_code == 201
    assert response.data["answer_count"] == 4
    assert response.data["submitted_at"] is not None
    assert response.data["activity_title"] == activity.title

    participant = Participant.objects.get(live_session=open_session)
    assert participant.has_submitted
    assert Response.objects.filter(participant=participant).count() == 4


def test_submitting_twice_is_rejected(api, open_session, activity, answers_for):
    token = join(api, open_session)
    payload = {"participant_token": token, "answers": answers_for(activity)}

    assert (
        api.post(
            submit_url(open_session.public_token), payload, format="json"
        ).status_code
        == 201
    )
    second = api.post(submit_url(open_session.public_token), payload, format="json")

    assert second.status_code == 409
    assert second.data["code"] == "already_submitted"
    assert Response.objects.filter(participant__live_session=open_session).count() == 4


def test_rejoining_after_submitting_is_refused(api, open_session, activity, answers_for):
    token = join(api, open_session, "Amara J")
    api.post(
        submit_url(open_session.public_token),
        {"participant_token": token, "answers": answers_for(activity)},
        format="json",
    )
    response = api.post(
        join_url(open_session.public_token), {"identifier": "Amara J"}, format="json"
    )
    assert response.status_code == 409
    assert response.data["code"] == "already_submitted"


def test_cannot_submit_to_a_closed_session(
    api, auth_client, open_session, activity, answers_for
):
    token = join(api, open_session)
    auth_client.post(reverse("livesession-close", args=[open_session.pk]))

    response = api.post(
        submit_url(open_session.public_token),
        {"participant_token": token, "answers": answers_for(activity)},
        format="json",
    )
    assert response.status_code == 409
    assert response.data["code"] == "session_closed"
    assert Response.objects.count() == 0


def test_an_invalid_participant_token_cannot_submit(
    api, open_session, activity, answers_for
):
    join(api, open_session)
    response = api.post(
        submit_url(open_session.public_token),
        {"participant_token": "f" * 32, "answers": answers_for(activity)},
        format="json",
    )
    assert response.status_code == 404
    assert Response.objects.count() == 0


def test_a_token_from_another_session_cannot_submit(
    api, auth_client, activity, open_session, answers_for
):
    other = auth_client.post(reverse("activity-launch", args=[activity.pk])).data
    token = join(api, open_session)

    response = api.post(
        submit_url(other["public_token"]),
        {"participant_token": token, "answers": answers_for(activity)},
        format="json",
    )
    assert response.status_code == 404


def test_missing_a_required_answer_is_rejected(api, open_session, activity, answers_for):
    token = join(api, open_session)
    answers = answers_for(activity)
    required_first = [
        answer
        for answer in answers
        if answer["question"] == activity.questions.get(position=1).pk
    ]
    remaining = [answer for answer in answers if answer not in required_first]

    response = api.post(
        submit_url(open_session.public_token),
        {"participant_token": token, "answers": remaining},
        format="json",
    )
    assert response.status_code == 400
    assert response.data["code"] == "required_answer_missing"
    assert Response.objects.count() == 0


def test_optional_question_may_be_left_blank(api, open_session, activity, answers_for):
    token = join(api, open_session)
    optional = activity.questions.get(position=3)
    answers = [a for a in answers_for(activity) if a["question"] != optional.pk]

    response = api.post(
        submit_url(open_session.public_token),
        {"participant_token": token, "answers": answers},
        format="json",
    )
    assert response.status_code == 201
    assert response.data["answer_count"] == 3


def test_a_choice_from_another_question_is_rejected(
    api, open_session, activity, answers_for
):
    token = join(api, open_session)
    mcq = activity.questions.get(position=1)
    answers = answers_for(activity)
    for answer in answers:
        if answer["question"] == mcq.pk:
            answer["selected_choice"] = 999_999

    response = api.post(
        submit_url(open_session.public_token),
        {"participant_token": token, "answers": answers},
        format="json",
    )
    assert response.status_code == 400
    assert response.data["code"] == "invalid_choice"


def test_an_answer_for_a_foreign_question_is_rejected(
    api, open_session, activity, make_activity, teacher, classroom, answers_for
):
    other_activity = make_activity(teacher, classroom, title="Unrelated")
    token = join(api, open_session)

    answers = answers_for(activity)
    answers.append(
        {"question": other_activity.questions.first().pk, "text_response": "x"}
    )
    response = api.post(
        submit_url(open_session.public_token),
        {"participant_token": token, "answers": answers},
        format="json",
    )
    assert response.status_code == 400


def test_out_of_range_confidence_is_rejected(api, open_session, activity, answers_for):
    token = join(api, open_session)
    answers = answers_for(activity)
    answers[0]["confidence_value"] = 9

    response = api.post(
        submit_url(open_session.public_token),
        {"participant_token": token, "answers": answers},
        format="json",
    )
    assert response.status_code == 400


def test_two_answers_for_one_question_are_rejected(
    api, open_session, activity, answers_for
):
    token = join(api, open_session)
    answers = answers_for(activity)
    answers.append(dict(answers[0]))

    response = api.post(
        submit_url(open_session.public_token),
        {"participant_token": token, "answers": answers},
        format="json",
    )
    assert response.status_code == 400
    assert Response.objects.count() == 0


def test_public_endpoints_need_no_authentication(
    api, open_session, activity, answers_for
):
    """The whole point: students never create an account."""
    assert api.get(lookup_url(), {"code": open_session.code}).status_code == 200
    assert api.get(session_url(open_session.public_token)).status_code == 200

    token = join(api, open_session)
    response = api.post(
        submit_url(open_session.public_token),
        {"participant_token": token, "answers": answers_for(activity)},
        format="json",
    )
    assert response.status_code == 201


def test_participant_token_is_never_returned_to_the_teacher(
    api, auth_client, open_session, activity, answers_for
):
    token = join(api, open_session)
    api.post(
        submit_url(open_session.public_token),
        {"participant_token": token, "answers": answers_for(activity)},
        format="json",
    )

    results = auth_client.get(reverse("livesession-results", args=[open_session.pk]))
    assert token not in str(results.data)
    assert "participant_token" not in str(results.data)
