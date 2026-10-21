"""CSV and JSON activity export."""

from __future__ import annotations

import csv
import io
import json

from caricue.activities.models import CHOICE_TYPES, Activity, QuestionType

from .activity_import import CSV_COLUMNS, SAMPLE_CSV


def activity_template_csv() -> str:
    return SAMPLE_CSV


def export_activity_json(activity: Activity) -> str:
    questions = []
    for question in (
        activity.questions.select_related("image")
        .prefetch_related("choices")
        .order_by("position")
    ):
        entry = {
            "position": question.position,
            "prompt": question.prompt,
            # Informational only: import ignores images, and the CSV format
            # has no column for them.
            "image_url": question.image_url,
            "image_alt": question.image_alt,
            "question_type": question.question_type,
            "rating_low_label": question.rating_low_label,
            "rating_high_label": question.rating_high_label,
            "is_required": question.is_required,
            "collect_confidence": question.collect_confidence,
            "accepted_answers": question.accepted_answers or [],
            "choices": [
                {
                    "text": choice.text,
                    "is_correct": choice.is_correct,
                    "position": choice.position,
                }
                for choice in question.choices.order_by("position")
            ],
        }
        questions.append(entry)
    payload = {
        "format_version": 1,
        "title": activity.title,
        "topic": activity.topic,
        "kind": activity.kind,
        "questions": questions,
    }
    return json.dumps(payload, indent=2)


def export_activity_csv(activity: Activity) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_COLUMNS)
    writer.writeheader()

    for question in activity.questions.prefetch_related("choices").order_by("position"):
        base = {
            "activity_title": activity.title,
            "activity_topic": activity.topic,
            "activity_kind": activity.kind,
            "rating_low_label": question.rating_low_label,
            "rating_high_label": question.rating_high_label,
            "question_position": question.position,
            "question_type": question.question_type,
            "prompt": question.prompt,
            "is_required": str(question.is_required).lower(),
            "collect_confidence": str(question.collect_confidence).lower(),
            "accepted_answers": "",
            "choice_position": "",
            "choice_text": "",
            "is_correct": "",
        }
        if question.question_type in CHOICE_TYPES:
            for choice in question.choices.order_by("position"):
                row = base.copy()
                row["choice_position"] = choice.position
                row["choice_text"] = choice.text
                row["is_correct"] = str(choice.is_correct).lower()
                writer.writerow(row)
        elif question.question_type == QuestionType.SHORT_TEXT:
            row = base.copy()
            answers = question.accepted_answers or []
            row["accepted_answers"] = "|".join(answers)
            writer.writerow(row)
        else:
            writer.writerow(base)

    return buffer.getvalue()
