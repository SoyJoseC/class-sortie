"""CSV and JSON activity import."""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, field

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from caricue.activities.models import ActivityStatus, QuestionType
from caricue.activities.serializers import ActivitySerializer
from caricue.classroom.models import Classroom

CSV_COLUMNS = (
    "activity_title",
    "activity_topic",
    "question_position",
    "question_type",
    "prompt",
    "is_required",
    "collect_confidence",
    "accepted_answers",
    "choice_position",
    "choice_text",
    "is_correct",
)

MAX_FILE_BYTES = 256 * 1024
MAX_ROWS = 50

SAMPLE_CSV = (
    "activity_title,activity_topic,question_position,question_type,prompt,is_required,"
    "collect_confidence,accepted_answers,choice_position,choice_text,is_correct\n"
    '"Networking check","Switches vs routers",1,multiple_choice,'
    '"Which device routes between networks?",true,true,,1,Switch,false\n'
    '"Networking check","Switches vs routers",1,multiple_choice,'
    '"Which device routes between networks?",true,true,,2,Router,true\n'
    '"Networking check","Switches vs routers",2,short_text,'
    '"What does LAN stand for?",true,false,"Local Area Network|local area network",,\n'
    '"Networking check","Switches vs routers",3,confidence,'
    '"How confident are you?",true,false,,,\n'
)


class ActivityImportError(Exception):
    """The file as a whole cannot be processed."""


@dataclass
class RowError:
    line: int
    message: str


@dataclass
class ImportResult:
    activity_id: int | None = None
    row_errors: list[RowError] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "activity_id": self.activity_id,
            "row_errors": [
                {"line": err.line, "message": err.message} for err in self.row_errors
            ],
        }


def _decode(raw: bytes) -> str:
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ActivityImportError("File could not be decoded as text. Please save as UTF-8.")


def _parse_bool(value: str, *, line: int, field_name: str) -> bool:
    cleaned = (value or "").strip().lower()
    if cleaned in {"true", "1", "yes"}:
        return True
    if cleaned in {"false", "0", "no"}:
        return False
    raise ValueError(f"Line {line}: {field_name} must be true or false.")


def _parse_activity_payload(data: dict) -> dict:
    questions = []
    for question in data.get("questions", []):
        q_type = question.get("question_type")
        if q_type not in QuestionType.values:
            raise ActivityImportError(f"Unknown question type {q_type!r}.")
        entry = {
            "prompt": (question.get("prompt") or "").strip(),
            "question_type": q_type,
            "is_required": bool(question.get("is_required", True)),
            "collect_confidence": bool(question.get("collect_confidence", False)),
            "accepted_answers": question.get("accepted_answers") or [],
            "choices": question.get("choices") or [],
        }
        questions.append(entry)
    title = (data.get("title") or "").strip()
    topic = (data.get("topic") or "").strip()
    if not title:
        raise ActivityImportError("Activity title is required.")
    return {
        "title": title,
        "topic": topic,
        "status": ActivityStatus.DRAFT,
        "questions": questions,
    }


def parse_activity_json(raw: bytes) -> dict:
    try:
        payload = json.loads(_decode(raw))
    except json.JSONDecodeError as exc:
        raise ActivityImportError("File is not valid JSON.") from exc
    if not isinstance(payload, dict):
        raise ActivityImportError("JSON root must be an object.")
    if "questions" not in payload and "title" in payload:
        return _parse_activity_payload(payload)
    if "format_version" in payload:
        return _parse_activity_payload(payload)
    raise ActivityImportError("JSON must include title, topic, and questions.")


def parse_activity_csv(raw: bytes) -> tuple[dict, list[RowError]]:
    text = _decode(raw)
    if not text.strip():
        raise ActivityImportError("The file is empty.")

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ActivityImportError("The CSV has no header row.")

    headers = {name.strip() for name in reader.fieldnames if name}
    missing = [col for col in CSV_COLUMNS if col not in headers]
    if missing:
        raise ActivityImportError(
            f"Missing required columns: {', '.join(missing)}."
        )

    row_errors: list[RowError] = []
    rows: list[tuple[int, dict[str, str]]] = []
    for line_number, row in enumerate(reader, start=2):
        if len(rows) + len(row_errors) >= MAX_ROWS:
            row_errors.append(
                RowError(line_number, f"At most {MAX_ROWS} data rows are allowed.")
            )
            break
        if not any((value or "").strip() for value in row.values()):
            continue
        rows.append((line_number, row))

    if not rows:
        raise ActivityImportError("The CSV has no data rows.")

    activity_title = rows[0][1]["activity_title"].strip()
    activity_topic = rows[0][1]["activity_topic"].strip()
    if not activity_title:
        raise ActivityImportError("activity_title is required on every row.")

    questions: dict[int, dict] = {}
    for line_number, row in rows:
        title = row["activity_title"].strip()
        topic = row["activity_topic"].strip()
        if title != activity_title or topic != activity_topic:
            row_errors.append(
                RowError(
                    line_number,
                    "All rows must share the same activity_title and activity_topic.",
                )
            )
            continue

        try:
            position = int(row["question_position"])
        except ValueError:
            row_errors.append(
                RowError(line_number, "question_position must be a whole number.")
            )
            continue

        q_type = row["question_type"].strip()
        if q_type not in QuestionType.values:
            row_errors.append(
                RowError(
                    line_number,
                    f"question_type must be one of: {', '.join(QuestionType.values)}.",
                )
            )
            continue

        prompt = row["prompt"].strip()
        if not prompt:
            row_errors.append(RowError(line_number, "prompt is required."))
            continue

        try:
            is_required = _parse_bool(
                row["is_required"], line=line_number, field_name="is_required"
            )
            collect_confidence = _parse_bool(
                row["collect_confidence"],
                line=line_number,
                field_name="collect_confidence",
            )
        except ValueError as exc:
            row_errors.append(RowError(line_number, str(exc)))
            continue

        question = questions.setdefault(
            position,
            {
                "prompt": prompt,
                "question_type": q_type,
                "is_required": is_required,
                "collect_confidence": collect_confidence,
                "accepted_answers": [],
                "choices": [],
            },
        )
        if question["prompt"] != prompt or question["question_type"] != q_type:
            row_errors.append(
                RowError(
                    line_number,
                    "Rows for the same question_position must agree on prompt and type.",
                )
            )
            continue

        if q_type == QuestionType.MULTIPLE_CHOICE:
            choice_text = row["choice_text"].strip()
            if not choice_text:
                row_errors.append(
                    RowError(
                        line_number,
                        "choice_text is required for multiple-choice rows.",
                    )
                )
                continue
            try:
                choice_position = int(row["choice_position"])
                is_correct = _parse_bool(
                    row["is_correct"], line=line_number, field_name="is_correct"
                )
            except ValueError as exc:
                row_errors.append(RowError(line_number, str(exc)))
                continue
            question["choices"].append(
                {
                    "position": choice_position,
                    "text": choice_text,
                    "is_correct": is_correct,
                }
            )
        elif q_type == QuestionType.SHORT_TEXT:
            accepted = row.get("accepted_answers", "").strip()
            if accepted:
                question["accepted_answers"] = [
                    part.strip() for part in accepted.split("|") if part.strip()
                ]
        elif row.get("choice_text", "").strip() or row.get("choice_position", "").strip():
            row_errors.append(
                RowError(line_number, "Only multiple-choice rows may include choices.")
            )

    if row_errors:
        return {}, row_errors

    ordered_questions = []
    for position in sorted(questions):
        question = questions[position]
        question["choices"] = sorted(question["choices"], key=lambda c: c["position"])
        for choice in question["choices"]:
            choice.pop("position", None)
        ordered_questions.append(question)

    payload = {
        "title": activity_title,
        "topic": activity_topic,
        "status": ActivityStatus.DRAFT,
        "questions": ordered_questions,
    }
    return payload, row_errors


def import_activity_file(
    *,
    classroom: Classroom,
    raw: bytes,
    filename: str,
    request,
) -> ImportResult:
    if len(raw) > MAX_FILE_BYTES:
        raise ActivityImportError(
            f"File is too large ({len(raw)} bytes). Maximum is {MAX_FILE_BYTES} bytes."
        )

    lowered = (filename or "").lower()
    if lowered.endswith(".json"):
        payload = parse_activity_json(raw)
        row_errors: list[RowError] = []
    elif lowered.endswith(".csv"):
        payload, row_errors = parse_activity_csv(raw)
        if row_errors:
            return ImportResult(row_errors=row_errors)
    else:
        raise ActivityImportError("Upload a .csv or .json file.")

    payload["classroom"] = classroom.pk
    serializer = ActivitySerializer(data=payload, context={"request": request})
    try:
        serializer.is_valid(raise_exception=True)
        activity = serializer.save()
    except serializers.ValidationError as exc:
        detail = exc.detail
        if isinstance(detail, dict):
            messages = []
            for key, value in detail.items():
                if isinstance(value, list):
                    messages.append(f"{key}: {' '.join(str(v) for v in value)}")
                else:
                    messages.append(f"{key}: {value}")
            raise ActivityImportError(" ".join(messages)) from exc
        raise ActivityImportError(str(detail)) from exc
    except DjangoValidationError as exc:
        raise ActivityImportError(str(exc)) from exc

    return ImportResult(activity_id=activity.pk, row_errors=row_errors)
