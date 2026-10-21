"""Surveys: unmarked activities with extra question types and anonymous join."""

from __future__ import annotations

import pytest
from django.urls import reverse

from caricue.activities.models import (
    Activity,
    ActivityKind,
    ActivityStatus,
    Choice,
    Question,
    QuestionType,
)
from caricue.live.models import Participant, Response
from caricue.live.services import launch_session

pytestmark = pytest.mark.django_db


def survey_payload(classroom, **overrides) -> dict:
    payload = {
        "classroom": classroom.pk,
        "title": "Unit feedback",
        "topic": "Networks",
        "kind": "survey",
        "questions": [
            {
                "prompt": "Which topics were useful?",
                "question_type": "multi_select",
                "choices": [{"text": "Cabling"}, {"text": "Switches"}, {"text": "Wi-Fi"}],
            },
            {
                "prompt": "How was the pace?",
                "question_type": "rating",
                "rating_low_label": "Too slow",
                "rating_high_label": "Too fast",
            },
            {
                "prompt": "Anything else?",
                "question_type": "short_text",
                "is_required": False,
            },
        ],
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def survey(teacher, classroom) -> Activity:
    activity = Activity.objects.create(
        teacher=teacher,
        classroom=classroom,
        title="Unit feedback",
        kind=ActivityKind.SURVEY,
    )
    multi = Question.objects.create(
        activity=activity,
        position=1,
        prompt="Which topics were useful?",
        question_type=QuestionType.MULTI_SELECT,
    )
    for position, text in enumerate(["Cabling", "Switches", "Wi-Fi"], start=1):
        Choice.objects.create(question=multi, text=text, position=position)
    Question.objects.create(
        activity=activity,
        position=2,
        prompt="How was the pace?",
        question_type=QuestionType.RATING,
        rating_low_label="Too slow",
        rating_high_label="Too fast",
    )
    Question.objects.create(
        activity=activity,
        position=3,
        prompt="Anything else?",
        question_type=QuestionType.SHORT_TEXT,
        is_required=False,
    )
    return activity


def anonymous_session(survey):
    session, error = launch_session(activity=survey, identity_mode="anonymous")
    assert error == ""
    return session


def join(api, session) -> str:
    response = api.post(
        reverse("public-join", args=[session.public_token]), {}, format="json"
    )
    assert response.status_code in (200, 201), response.data
    return response.data["participant_token"]


def submit(api, session, token, answers):
    return api.post(
        reverse("public-submit", args=[session.public_token]),
        {"participant_token": token, "answers": answers},
        format="json",
    )


# --------------------------------------------------------------------------- #
# Authoring
# --------------------------------------------------------------------------- #
def test_a_survey_can_be_created_without_an_answer_key(auth_client, classroom):
    response = auth_client.post(
        reverse("activity-list"), survey_payload(classroom), format="json"
    )

    assert response.status_code == 201, response.data
    assert response.data["kind"] == "survey"
    multi, rating, text = response.data["questions"]
    assert multi["question_type"] == "multi_select"
    assert not any(choice["is_correct"] for choice in multi["choices"])
    assert rating["rating_low_label"] == "Too slow"
    assert multi["is_auto_scored"] is False
    assert text["is_auto_scored"] is False


def test_a_survey_discards_any_answer_key_it_is_sent(auth_client, classroom):
    payload = survey_payload(classroom)
    payload["questions"][0]["choices"][0]["is_correct"] = True
    payload["questions"].append(
        {
            "prompt": "Name a device",
            "question_type": "short_text",
            "accepted_answers": ["router"],
            "collect_confidence": True,
        }
    )

    response = auth_client.post(reverse("activity-list"), payload, format="json")

    assert response.status_code == 201, response.data
    questions = response.data["questions"]
    assert not any(c["is_correct"] for c in questions[0]["choices"])
    assert questions[-1]["accepted_answers"] == []
    assert questions[-1]["collect_confidence"] is False


def test_a_survey_rejects_a_confidence_question(auth_client, classroom):
    payload = survey_payload(classroom)
    payload["questions"].append({"prompt": "Confident?", "question_type": "confidence"})

    response = auth_client.post(reverse("activity-list"), payload, format="json")

    assert response.status_code == 400
    assert "Question 4" in str(response.data["errors"]["questions"])


def test_a_quiz_rejects_survey_only_question_types(auth_client, classroom):
    payload = survey_payload(classroom, kind="quiz")

    response = auth_client.post(reverse("activity-list"), payload, format="json")

    assert response.status_code == 400
    assert "only for surveys" in str(response.data["errors"]["questions"])


def test_a_quiz_still_needs_a_correct_choice(auth_client, classroom):
    payload = {
        "classroom": classroom.pk,
        "title": "Quiz",
        "questions": [
            {
                "prompt": "Pick one",
                "question_type": "multiple_choice",
                "choices": [{"text": "A"}, {"text": "B"}],
            }
        ],
    }

    response = auth_client.post(reverse("activity-list"), payload, format="json")

    assert response.status_code == 400
    assert "correct" in str(response.data["errors"]["questions"])


def test_multi_select_needs_two_distinct_choices(auth_client, classroom):
    payload = survey_payload(classroom)
    payload["questions"][0]["choices"] = [{"text": "Only"}]

    response = auth_client.post(reverse("activity-list"), payload, format="json")

    assert response.status_code == 400


def test_non_rating_questions_drop_rating_labels(auth_client, classroom):
    payload = survey_payload(classroom)
    payload["questions"][2]["rating_low_label"] = "Low"

    response = auth_client.post(reverse("activity-list"), payload, format="json")

    assert response.status_code == 201, response.data
    assert response.data["questions"][2]["rating_low_label"] == ""


def test_kind_is_locked_once_a_session_has_been_launched(auth_client, survey):
    anonymous_session(survey)
    detail = reverse("activity-detail", args=[survey.pk])

    response = auth_client.patch(detail, {"kind": "quiz"}, format="json")

    assert response.status_code == 400
    assert "kind" in response.data["errors"]


def test_kind_can_change_before_any_launch(auth_client, teacher, classroom):
    activity = Activity.objects.create(
        teacher=teacher, classroom=classroom, title="Draft"
    )
    detail = reverse("activity-detail", args=[activity.pk])

    response = auth_client.patch(detail, {"kind": "survey"}, format="json")

    assert response.status_code == 200, response.data
    assert response.data["kind"] == "survey"


def test_activity_list_reports_the_kind(auth_client, survey):
    response = auth_client.get(reverse("activity-list"))

    rows = response.data["results"] if isinstance(response.data, dict) else response.data
    assert rows[0]["kind"] == "survey"


# --------------------------------------------------------------------------- #
# Launching
# --------------------------------------------------------------------------- #
def test_a_survey_without_a_correct_choice_is_launchable(survey):
    launchable, reason = survey.is_launchable()

    assert launchable, reason


def test_anonymous_join_is_refused_for_quizzes(activity, enrolled_students):
    session, error = launch_session(activity=activity, identity_mode="anonymous")

    assert session is None
    assert "survey" in error.lower()


def test_a_quiz_cannot_hold_survey_only_types_at_launch(teacher, classroom):
    quiz = Activity.objects.create(teacher=teacher, classroom=classroom, title="Odd")
    Question.objects.create(
        activity=quiz, position=1, prompt="Rate it", question_type=QuestionType.RATING
    )

    launchable, _ = quiz.is_launchable()

    assert not launchable


# --------------------------------------------------------------------------- #
# Joining and submitting
# --------------------------------------------------------------------------- #
def test_anonymous_join_needs_no_name(api, survey):
    session = anonymous_session(survey)

    first = join(api, session)
    second = join(api, session)

    assert first != second
    names = set(Participant.objects.values_list("display_name", flat=True))
    assert names == {"Respondent 1", "Respondent 2"}
    assert not Participant.objects.filter(student__isnull=False).exists()


def test_public_session_describes_a_survey_without_keys(api, survey):
    session = anonymous_session(survey)

    response = api.get(reverse("public-session", args=[session.public_token]))

    assert response.status_code == 200
    assert response.data["activity_kind"] == "survey"
    assert response.data["identity_mode"] == "anonymous"
    rating = response.data["questions"][1]
    assert rating["rating_low_label"] == "Too slow"
    for question in response.data["questions"]:
        for choice in question["choices"]:
            assert "is_correct" not in choice


def test_a_survey_submission_stores_choices_and_rating_unmarked(api, survey):
    session = anonymous_session(survey)
    token = join(api, session)
    multi, rating, text = survey.questions.order_by("position")
    picked = list(multi.choices.order_by("position").values_list("pk", flat=True)[:2])

    response = submit(
        api,
        session,
        token,
        [
            {"question": multi.pk, "selected_choices": picked},
            {"question": rating.pk, "rating_value": 4},
            {"question": text.pk, "text_response": "More labs please"},
        ],
    )

    assert response.status_code == 201, response.data
    stored = {r.question_id: r for r in Response.objects.all()}
    assert set(stored[multi.pk].selected_choices.values_list("pk", flat=True)) == set(
        picked
    )
    assert stored[rating.pk].rating_value == 4
    assert all(r.is_correct is None for r in stored.values())


def test_an_optional_text_answer_may_be_skipped(api, survey):
    session = anonymous_session(survey)
    token = join(api, session)
    multi, rating, _ = survey.questions.order_by("position")

    response = submit(
        api,
        session,
        token,
        [
            {"question": multi.pk, "selected_choices": [multi.choices.first().pk]},
            {"question": rating.pk, "rating_value": 1},
        ],
    )

    assert response.status_code == 201, response.data


def test_a_required_multi_select_cannot_be_left_empty(api, survey):
    session = anonymous_session(survey)
    token = join(api, session)
    multi, rating, _ = survey.questions.order_by("position")

    response = submit(
        api,
        session,
        token,
        [
            {"question": multi.pk, "selected_choices": []},
            {"question": rating.pk, "rating_value": 3},
        ],
    )

    assert response.status_code == 400


@pytest.mark.parametrize("value", [0, 6, -1])
def test_a_rating_outside_the_scale_is_rejected(api, survey, value):
    session = anonymous_session(survey)
    token = join(api, session)
    multi, rating, _ = survey.questions.order_by("position")

    response = submit(
        api,
        session,
        token,
        [
            {"question": multi.pk, "selected_choices": [multi.choices.first().pk]},
            {"question": rating.pk, "rating_value": value},
        ],
    )

    assert response.status_code == 400


def test_multi_select_rejects_a_choice_from_another_question(api, survey, activity):
    session = anonymous_session(survey)
    token = join(api, session)
    multi, rating, _ = survey.questions.order_by("position")
    foreign = Choice.objects.filter(question__activity=activity).first()

    response = submit(
        api,
        session,
        token,
        [
            {"question": multi.pk, "selected_choices": [foreign.pk]},
            {"question": rating.pk, "rating_value": 3},
        ],
    )

    assert response.status_code == 400
    assert not Response.objects.exists()


def test_survey_status_is_published_after_launch(survey):
    anonymous_session(survey)
    survey.refresh_from_db()

    assert survey.status == ActivityStatus.PUBLISHED


# --------------------------------------------------------------------------- #
# Insights, exports and the quiz-only features
# --------------------------------------------------------------------------- #
def filled_session(api, survey, respondents):
    session = anonymous_session(survey)
    multi, rating, text = survey.questions.order_by("position")
    choices = list(multi.choices.order_by("position"))
    for picks, score, comment in respondents:
        token = join(api, session)
        answers = [
            {"question": multi.pk, "selected_choices": [choices[i].pk for i in picks]},
            {"question": rating.pk, "rating_value": score},
        ]
        if comment:
            answers.append({"question": text.pk, "text_response": comment})
        assert submit(api, session, token, answers).status_code == 201
    return session


def test_survey_insights_summarise_choices_ratings_and_text(api, survey):
    from caricue.insights.service import build_session_insights

    session = filled_session(
        api, survey, [([0, 1], 4, "More labs"), ([1], 2, ""), ([1, 2], 4, "More labs!")]
    )

    insights = build_session_insights(session)

    assert insights.activity_kind == "survey"
    assert insights.needs_attention == []
    assert insights.overall_correctness_percentage is None
    multi, rating, text = insights.questions
    counts = {c.text: c.count for c in multi.choice_breakdown}
    assert counts == {"Cabling": 1, "Switches": 3, "Wi-Fi": 1}
    assert rating.rating_distribution == {"1": 0, "2": 1, "3": 0, "4": 2, "5": 0}
    assert rating.average_rating == pytest.approx(3.33, abs=0.01)
    assert text.text_answers == ["More labs", "More labs!"]  # verbatim, not grouped


def test_survey_dashboard_has_no_quiz_panels(auth_client, api, survey):
    session = filled_session(api, survey, [([0], 5, "ok")])

    response = auth_client.get(reverse("livesession-dashboard", args=[session.pk]))

    assert response.status_code == 200
    assert response.data["suggestions"] == []
    assert response.data["misconception_cards"] == []
    assert response.data["facts"]["activity_kind"] == "survey"


def test_survey_results_list_each_respondents_answers(auth_client, api, survey):
    session = filled_session(api, survey, [([0, 2], 3, "")])

    response = auth_client.get(reverse("livesession-results", args=[session.pk]))

    assert response.status_code == 200
    answers = response.data["participants"][0]["responses"]
    by_type = {a["question_type"]: a for a in answers}
    assert by_type["rating"]["rating_value"] == 3
    assert sorted(by_type["multi_select"]["selected_choice_texts"]) == [
        "Cabling",
        "Wi-Fi",
    ]
    assert all(a["is_correct"] is None for a in answers)


def test_a_survey_has_no_follow_up(auth_client, api, survey, teacher):
    from caricue.activities.follow_up import create_follow_up_activity

    session = filled_session(api, survey, [([0], 1, "")])

    with pytest.raises(ValueError):
        create_follow_up_activity(session, teacher)
    response = auth_client.post(
        reverse("livesession-follow-up-activity", args=[session.pk]), {}, format="json"
    )
    assert response.status_code == 400


def test_surveys_never_produce_a_comparison(api, survey):
    from caricue.insights.comparison import build_session_comparison
    from caricue.live.services import close_session

    session = filled_session(api, survey, [([0], 1, "")])
    close_session(session)
    session.refresh_from_db()

    assert build_session_comparison(session) is None


def test_survey_round_trips_through_json_export_and_import(
    auth_client, survey, classroom
):
    from caricue.activities.activity_export import export_activity_json
    from caricue.activities.activity_import import parse_activity_json

    payload = parse_activity_json(export_activity_json(survey).encode())

    assert payload["kind"] == "survey"
    assert payload["questions"][1]["rating_low_label"] == "Too slow"
    assert [q["question_type"] for q in payload["questions"]] == [
        "multi_select",
        "rating",
        "short_text",
    ]


def test_survey_round_trips_through_csv_export_and_import(survey):
    from caricue.activities.activity_export import export_activity_csv
    from caricue.activities.activity_import import parse_activity_csv

    payload, errors = parse_activity_csv(export_activity_csv(survey).encode())

    assert errors == []
    assert payload["kind"] == "survey"
    multi = payload["questions"][0]
    assert [c["text"] for c in multi["choices"]] == ["Cabling", "Switches", "Wi-Fi"]
    assert payload["questions"][1]["rating_high_label"] == "Too fast"


def test_csv_files_from_before_surveys_still_import():
    from caricue.activities.activity_import import SAMPLE_CSV, parse_activity_csv

    payload, errors = parse_activity_csv(SAMPLE_CSV.encode())

    assert errors == []
    assert payload["kind"] == "quiz"
