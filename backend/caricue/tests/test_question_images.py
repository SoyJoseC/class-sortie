"""Question images: upload validation, ownership, attachment, serving payloads."""

from __future__ import annotations

import io
from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from caricue.activities.models import QuestionImage, QuestionType

pytestmark = pytest.mark.django_db


def make_image_bytes(
    fmt: str = "PNG", size: tuple[int, int] = (64, 48), mode: str = "RGB"
) -> bytes:
    buffer = io.BytesIO()
    Image.new(mode, size, (200, 30, 30) if mode == "RGB" else (200, 30, 30, 128)).save(
        buffer, format=fmt
    )
    return buffer.getvalue()


def upload(client, content: bytes, name: str = "diagram.png", ctype: str = "image/png"):
    return client.post(
        reverse("questionimage-list"),
        {"file": SimpleUploadedFile(name, content, content_type=ctype)},
        format="multipart",
    )


def test_upload_returns_id_url_and_dimensions(auth_client):
    response = upload(auth_client, make_image_bytes())

    assert response.status_code == 201
    assert response.data["url"].startswith("/media/question-images/")
    assert response.data["width"] == 64
    assert response.data["height"] == 48
    assert "file" not in response.data


def test_original_filename_is_not_kept(auth_client):
    response = upload(auth_client, make_image_bytes(), name="my-secret-name.png")
    stored = QuestionImage.objects.get(pk=response.data["id"])
    assert "my-secret-name" not in stored.file.name


def test_large_images_are_downscaled(auth_client, settings):
    settings.CARICUE = {**settings.CARICUE, "MAX_IMAGE_EDGE_PX": 100}
    response = upload(auth_client, make_image_bytes(size=(400, 200)))
    assert response.status_code == 201
    assert max(response.data["width"], response.data["height"]) == 100


def test_exif_is_stripped_on_reencode(auth_client):
    image = Image.new("RGB", (40, 40), (10, 200, 10))
    exif = Image.Exif()
    exif[0x010E] = "secret description"  # ImageDescription
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", exif=exif)
    assert b"secret description" in buffer.getvalue()

    response = upload(auth_client, buffer.getvalue(), "photo.jpg", "image/jpeg")

    assert response.status_code == 201
    stored = QuestionImage.objects.get(pk=response.data["id"])
    with stored.file.open("rb") as handle:
        assert b"secret description" not in handle.read()


def test_non_images_are_rejected_whatever_they_claim(auth_client):
    response = upload(auth_client, b"<script>alert(1)</script>", "x.png", "image/png")
    assert response.status_code == 400
    assert "file" in response.data["errors"]
    assert QuestionImage.objects.count() == 0


def test_unsupported_formats_are_rejected(auth_client):
    gif = make_image_bytes(fmt="GIF")
    response = upload(auth_client, gif, "x.gif", "image/gif")
    assert response.status_code == 400
    assert QuestionImage.objects.count() == 0


def test_oversized_uploads_are_rejected(auth_client, settings):
    settings.CARICUE = {**settings.CARICUE, "MAX_IMAGE_BYTES": 500}
    response = upload(auth_client, make_image_bytes(size=(300, 300)))
    assert response.status_code == 400
    assert "too large" in str(response.data["errors"]["file"]).lower()


def test_upload_requires_a_teacher_session(api):
    response = upload(api, make_image_bytes())
    assert response.status_code in (401, 403)


def test_teachers_cannot_read_or_delete_each_others_images(auth_client, other_client):
    image_id = upload(auth_client, make_image_bytes()).data["id"]
    detail = reverse("questionimage-detail", args=[image_id])

    assert other_client.get(detail).status_code == 404
    assert other_client.delete(detail).status_code == 404
    assert auth_client.get(detail).status_code == 200


def test_deleting_an_image_removes_the_file(auth_client):
    created = upload(auth_client, make_image_bytes())
    stored = QuestionImage.objects.get(pk=created.data["id"])
    path = stored.file.path

    response = auth_client.delete(reverse("questionimage-detail", args=[stored.pk]))

    assert response.status_code == 204
    import os

    assert not os.path.exists(path)


def question_payload(image_id=None, alt="A network diagram"):
    payload = {
        "prompt": "What does the diagram show?",
        "question_type": QuestionType.SHORT_TEXT,
        "accepted_answers": ["a network"],
    }
    if image_id is not None:
        payload["image_id"] = image_id
        payload["image_alt"] = alt
    return payload


def test_image_attaches_to_a_question_and_appears_in_every_payload(
    auth_client, classroom
):
    image_id = upload(auth_client, make_image_bytes()).data["id"]
    created = auth_client.post(
        reverse("activity-list"),
        {
            "classroom": classroom.pk,
            "title": "Diagram check",
            "questions": [question_payload(image_id)],
        },
        format="json",
    )

    assert created.status_code == 201
    question = created.data["questions"][0]
    assert question["image_id"] == image_id
    assert question["image_url"].startswith("/media/")
    assert question["image_alt"] == "A network diagram"

    preview = auth_client.get(reverse("activity-preview", args=[created.data["id"]]))
    assert preview.data["questions"][0]["image_url"] == question["image_url"]


def test_image_survives_resaving_and_can_be_removed(auth_client, classroom):
    image_id = upload(auth_client, make_image_bytes()).data["id"]
    created = auth_client.post(
        reverse("activity-list"),
        {
            "classroom": classroom.pk,
            "title": "Diagram check",
            "questions": [question_payload(image_id)],
        },
        format="json",
    ).data
    detail = reverse("activity-detail", args=[created["id"]])

    # Saving again without mentioning the image leaves it alone.
    kept = created["questions"][0] | {"prompt": "Reworded"}
    kept.pop("image_id")
    resaved = auth_client.put(
        detail,
        {"classroom": classroom.pk, "title": "Diagram check", "questions": [kept]},
        format="json",
    )
    assert resaved.data["questions"][0]["image_id"] == image_id

    # An explicit null detaches it and clears the alt text.
    removed = resaved.data["questions"][0] | {"image_id": None}
    final = auth_client.put(
        detail,
        {"classroom": classroom.pk, "title": "Diagram check", "questions": [removed]},
        format="json",
    )
    assert final.data["questions"][0]["image_id"] is None
    assert final.data["questions"][0]["image_url"] is None
    assert final.data["questions"][0]["image_alt"] == ""


def test_a_teacher_cannot_attach_someone_elses_image(
    auth_client, other_client, classroom
):
    foreign_id = upload(other_client, make_image_bytes()).data["id"]

    response = auth_client.post(
        reverse("activity-list"),
        {
            "classroom": classroom.pk,
            "title": "Nope",
            "questions": [question_payload(foreign_id)],
        },
        format="json",
    )

    assert response.status_code == 400


def test_students_receive_the_image_but_never_the_answer_key(api, auth_client, classroom):
    image_id = upload(auth_client, make_image_bytes()).data["id"]
    activity = auth_client.post(
        reverse("activity-list"),
        {
            "classroom": classroom.pk,
            "title": "Diagram check",
            "questions": [question_payload(image_id)],
        },
        format="json",
    ).data
    launched = auth_client.post(
        reverse("activity-launch", args=[activity["id"]]), {}, format="json"
    ).data

    public = api.get(reverse("public-session", args=[launched["public_token"]]))

    assert public.status_code == 200
    question = public.data["questions"][0]
    assert question["image_url"].startswith("/media/")
    assert question["image_alt"] == "A network diagram"
    assert "accepted_answers" not in str(public.data)


def test_prune_removes_only_old_unattached_images(auth_client, classroom):
    attached_id = upload(auth_client, make_image_bytes()).data["id"]
    auth_client.post(
        reverse("activity-list"),
        {
            "classroom": classroom.pk,
            "title": "Diagram check",
            "questions": [question_payload(attached_id)],
        },
        format="json",
    )
    old_orphan = upload(auth_client, make_image_bytes()).data["id"]
    fresh_orphan = upload(auth_client, make_image_bytes()).data["id"]
    QuestionImage.objects.filter(pk__in=[attached_id, old_orphan]).update(
        created_at=timezone.now() - timedelta(days=3)
    )

    call_command("prune_orphan_images")

    remaining = set(QuestionImage.objects.values_list("pk", flat=True))
    assert remaining == {attached_id, fresh_orphan}
