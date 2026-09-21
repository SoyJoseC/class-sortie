"""CSV roster import.

For the MVP this replaces direct Moodle synchronisation: a teacher exports a
participants list, trims it to the columns below, and uploads it.

Contract
--------
Required column: ``display_name``
Optional columns: ``school_identifier``, ``email``

The import is *idempotent per teacher*: a row whose ``school_identifier``
already exists for this teacher updates that student and (re)activates their
enrolment instead of creating a duplicate. Rows without an identifier are
matched on a case-insensitive display name within the same class.

Every row is validated independently; valid rows are applied and invalid rows
are reported back with their line number so the teacher can fix the file.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django.db import transaction

from .models import Classroom, Enrollment, Student

REQUIRED_COLUMNS = ("display_name",)
OPTIONAL_COLUMNS = ("school_identifier", "email")
ALL_COLUMNS = REQUIRED_COLUMNS + OPTIONAL_COLUMNS

MAX_FILE_BYTES = 512 * 1024
MAX_ROWS = 500

SAMPLE_CSV = (
    "display_name,school_identifier,email\n"
    "Amara Joseph,STU-001,\n"
    "Devon Charles,STU-002,\n"
    "Keisha Boodram,STU-003,keisha.b@example.edu\n"
    "Rohan Persad,STU-004,\n"
)


class RosterImportError(Exception):
    """The file as a whole cannot be processed."""


@dataclass
class RowError:
    line: int
    message: str


@dataclass
class ImportResult:
    created_students: int = 0
    updated_students: int = 0
    created_enrollments: int = 0
    reactivated_enrollments: int = 0
    skipped_rows: int = 0
    row_errors: list[RowError] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "created_students": self.created_students,
            "updated_students": self.updated_students,
            "created_enrollments": self.created_enrollments,
            "reactivated_enrollments": self.reactivated_enrollments,
            "skipped_rows": self.skipped_rows,
            "row_errors": [
                {"line": err.line, "message": err.message} for err in self.row_errors
            ],
        }


def _decode(raw: bytes) -> str:
    if len(raw) > MAX_FILE_BYTES:
        raise RosterImportError(
            f"File is too large. The limit is {MAX_FILE_BYTES // 1024} KB."
        )
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise RosterImportError("File could not be decoded as text. Please save as UTF-8.")


def _normalize_header(name: str | None) -> str:
    return (name or "").strip().lower().replace(" ", "_").replace("-", "_")


@transaction.atomic
def import_roster_csv(*, classroom: Classroom, raw: bytes) -> ImportResult:
    """Applies `raw` CSV content to `classroom`'s roster."""
    text = _decode(raw)
    reader = csv.DictReader(io.StringIO(text))

    if reader.fieldnames is None:
        raise RosterImportError("The file is empty.")

    header_map = {_normalize_header(name): name for name in reader.fieldnames}
    missing = [col for col in REQUIRED_COLUMNS if col not in header_map]
    if missing:
        raise RosterImportError(
            "Missing required column(s): "
            + ", ".join(missing)
            + f". Expected header: {','.join(ALL_COLUMNS)}"
        )

    result = ImportResult()
    teacher = classroom.teacher
    seen_identifiers: set[str] = set()
    seen_names: set[str] = set()

    for index, row in enumerate(reader, start=2):  # line 1 is the header
        if index - 1 > MAX_ROWS:
            result.row_errors.append(RowError(index, f"Stopped after {MAX_ROWS} rows."))
            break

        display_name = (row.get(header_map["display_name"]) or "").strip()
        identifier = (
            (row.get(header_map.get("school_identifier", "")) or "").strip()
            if "school_identifier" in header_map
            else ""
        )
        email = (
            (row.get(header_map.get("email", "")) or "").strip()
            if "email" in header_map
            else ""
        )

        if not display_name and not identifier and not email:
            result.skipped_rows += 1
            continue

        if not display_name:
            result.row_errors.append(RowError(index, "display_name is required."))
            continue
        if len(display_name) > 120:
            result.row_errors.append(
                RowError(index, "display_name exceeds 120 characters.")
            )
            continue
        if len(identifier) > 60:
            result.row_errors.append(
                RowError(index, "school_identifier exceeds 60 characters.")
            )
            continue
        if email:
            try:
                validate_email(email)
            except DjangoValidationError:
                result.row_errors.append(
                    RowError(index, f"{email!r} is not a valid email.")
                )
                continue

        dedupe_key = identifier.lower() if identifier else display_name.lower()
        bucket = seen_identifiers if identifier else seen_names
        if dedupe_key in bucket:
            result.row_errors.append(
                RowError(index, f"Duplicate row for {display_name!r} in this file.")
            )
            continue
        bucket.add(dedupe_key)

        student = _resolve_student(
            teacher=teacher,
            classroom=classroom,
            display_name=display_name,
            identifier=identifier,
        )

        if student is None:
            student = Student.objects.create(
                teacher=teacher,
                display_name=display_name,
                school_identifier=identifier,
                email=email,
            )
            result.created_students += 1
        else:
            changed = []
            if student.display_name != display_name:
                student.display_name = display_name
                changed.append("display_name")
            if identifier and student.school_identifier != identifier:
                student.school_identifier = identifier
                changed.append("school_identifier")
            if email and student.email != email:
                student.email = email
                changed.append("email")
            if not student.is_active:
                student.is_active = True
                changed.append("is_active")
            if changed:
                student.save(update_fields=[*changed, "updated_at"])
                result.updated_students += 1

        enrollment, created = Enrollment.objects.get_or_create(
            classroom=classroom,
            student=student,
            defaults={"is_active": True},
        )
        if created:
            result.created_enrollments += 1
        elif not enrollment.is_active:
            enrollment.is_active = True
            enrollment.save(update_fields=["is_active", "updated_at"])
            result.reactivated_enrollments += 1

    return result


def _resolve_student(
    *, teacher, classroom: Classroom, display_name: str, identifier: str
) -> Student | None:
    if identifier:
        return Student.objects.filter(
            teacher=teacher, school_identifier__iexact=identifier
        ).first()
    # No identifier: only reuse a student already enrolled in *this* class, so
    # two classes can legitimately contain different students with the same
    # common name.
    return Student.objects.filter(
        teacher=teacher,
        display_name__iexact=display_name,
        enrollments__classroom=classroom,
    ).first()
