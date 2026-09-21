from __future__ import annotations

from rest_framework import serializers

from .models import Classroom, Enrollment, Student


class ClassroomSerializer(serializers.ModelSerializer):
    """List views annotate these counts; single-object writes fall back to a
    query, so a freshly created class still reports them."""

    roster_size = serializers.SerializerMethodField()
    activity_count = serializers.SerializerMethodField()

    class Meta:
        model = Classroom
        fields = [
            "id",
            "name",
            "subject",
            "level",
            "academic_period",
            "is_active",
            "roster_size",
            "activity_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_roster_size(self, classroom: Classroom) -> int:
        annotated = getattr(classroom, "enrolled_count", None)
        return annotated if annotated is not None else classroom.roster_size

    def get_activity_count(self, classroom: Classroom) -> int:
        annotated = getattr(classroom, "activities_total", None)
        return annotated if annotated is not None else classroom.activities.count()

    def validate_name(self, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise serializers.ValidationError("Class name is required.")
        teacher = self.context["request"].user
        clash = Classroom.objects.filter(teacher=teacher, name__iexact=cleaned)
        if self.instance is not None:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError("You already have a class with this name.")
        return cleaned

    def create(self, validated_data: dict) -> Classroom:
        validated_data["teacher"] = self.context["request"].user
        return super().create(validated_data)


class StudentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Student
        fields = [
            "id",
            "display_name",
            "school_identifier",
            "email",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_display_name(self, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise serializers.ValidationError("Display name is required.")
        return cleaned

    def validate_school_identifier(self, value: str) -> str:
        cleaned = (value or "").strip()
        if not cleaned:
            return ""
        teacher = self.context["request"].user
        clash = Student.objects.filter(teacher=teacher, school_identifier__iexact=cleaned)
        if self.instance is not None:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError(
                "Another student already uses this identifier."
            )
        return cleaned

    def create(self, validated_data: dict) -> Student:
        validated_data["teacher"] = self.context["request"].user
        return super().create(validated_data)


class EnrollmentSerializer(serializers.ModelSerializer):
    student_detail = StudentSerializer(source="student", read_only=True)

    class Meta:
        model = Enrollment
        fields = [
            "id",
            "classroom",
            "student",
            "student_detail",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def validate(self, attrs: dict) -> dict:
        teacher = self.context["request"].user
        classroom = attrs.get("classroom") or getattr(self.instance, "classroom", None)
        student = attrs.get("student") or getattr(self.instance, "student", None)

        # Cross-tenant guard: both sides of the relation must be owned by the
        # requesting teacher, otherwise a valid id from another account could
        # be used to attach a foreign student to your class.
        if classroom is not None and classroom.teacher_id != teacher.pk:
            raise serializers.ValidationError({"classroom": "Class not found."})
        if student is not None and student.teacher_id != teacher.pk:
            raise serializers.ValidationError({"student": "Student not found."})

        if classroom is not None and student is not None:
            clash = Enrollment.objects.filter(classroom=classroom, student=student)
            if self.instance is not None:
                clash = clash.exclude(pk=self.instance.pk)
            if clash.exists():
                raise serializers.ValidationError(
                    {"student": "This student is already in the class."}
                )
        return attrs


class AddStudentToClassSerializer(serializers.Serializer):
    """Creates a student and enrols them in one request (manual add flow)."""

    display_name = serializers.CharField(max_length=120)
    school_identifier = serializers.CharField(
        max_length=60, required=False, allow_blank=True, default=""
    )
    email = serializers.EmailField(
        max_length=254, required=False, allow_blank=True, default=""
    )

    def validate_display_name(self, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise serializers.ValidationError("Display name is required.")
        return cleaned

    def validate_school_identifier(self, value: str) -> str:
        return (value or "").strip()


class RosterImportSerializer(serializers.Serializer):
    file = serializers.FileField()

    def validate_file(self, upload):
        name = (upload.name or "").lower()
        if not name.endswith(".csv"):
            raise serializers.ValidationError("Please upload a .csv file.")
        return upload
