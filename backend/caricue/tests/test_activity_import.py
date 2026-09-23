"""Activity CSV/JSON import and export."""

from __future__ import annotations

import json

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from caricue.activities.activity_export import export_activity_csv, export_activity_json
from caricue.activities.activity_import import SAMPLE_CSV
from caricue.activities.models import Activity

pytestmark = pytest.mark.django_db


def test_activity_template_endpoint(auth_client):
    response = auth_client.get("/api/activities/template.csv/")

    assert response.status_code == 200
    assert "activity_title" in response.content.decode()
    assert response["Content-Disposition"].startswith("attachment")


def test_import_valid_csv_creates_draft(auth_client, classroom):
    response = auth_client.post(
        "/api/activities/import/",
        {
            "classroom": classroom.pk,
            "file": SimpleUploadedFile("check.csv", SAMPLE_CSV.encode(), "text/csv"),
        },
        format="multipart",
    )

    assert response.status_code == 201, response.data
    activity = Activity.objects.get(pk=response.data["activity_id"])
    assert activity.status == "draft"
    assert activity.questions.count() == 3
    assert activity.questions.filter(question_type="multiple_choice").exists()


def test_import_rejects_mcq_without_correct(auth_client, classroom):
    csv_body = (
        "activity_title,activity_topic,question_position,question_type,prompt,is_required,"
        "collect_confidence,accepted_answers,choice_position,choice_text,is_correct\n"
        '"Bad","Topic",1,multiple_choice,"Pick one",true,false,,1,Only,false\n'
        '"Bad","Topic",1,multiple_choice,"Pick one",true,false,,2,Other,false\n'
    )
    response = auth_client.post(
        "/api/activities/import/",
        {
            "classroom": classroom.pk,
            "file": SimpleUploadedFile("bad.csv", csv_body.encode(), "text/csv"),
        },
        format="multipart",
    )

    assert response.status_code == 400


def test_json_round_trip(auth_client, activity):
    exported = export_activity_json(activity)
    response = auth_client.post(
        "/api/activities/import/",
        {
            "classroom": activity.classroom_id,
            "file": SimpleUploadedFile(
                "roundtrip.json", exported.encode(), "application/json"
            ),
        },
        format="multipart",
    )

    assert response.status_code == 201, response.data
    imported = Activity.objects.get(pk=response.data["activity_id"])
    assert imported.title == activity.title
    assert imported.questions.count() == activity.questions.count()


def test_export_csv_other_teacher_gets_404(other_client, activity):
    response = other_client.get(f"/api/activities/{activity.pk}/export.csv/")

    assert response.status_code == 404


def test_export_json_matches_structure(activity):
    payload = json.loads(export_activity_json(activity))
    assert payload["format_version"] == 1
    assert payload["title"] == activity.title
    assert len(payload["questions"]) == activity.questions.count()


def test_export_csv_has_header_row(activity):
    csv_text = export_activity_csv(activity)
    assert "activity_title" in csv_text.splitlines()[0]
