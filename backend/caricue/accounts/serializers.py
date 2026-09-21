from __future__ import annotations

from django.contrib.auth import authenticate, password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import Teacher


class TeacherSerializer(serializers.ModelSerializer):
    class Meta:
        model = Teacher
        fields = ["id", "email", "full_name", "school_name", "date_joined"]
        read_only_fields = ["id", "email", "date_joined"]


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    full_name = serializers.CharField(max_length=150)
    school_name = serializers.CharField(
        max_length=150, required=False, allow_blank=True, default=""
    )
    password = serializers.CharField(write_only=True, min_length=10, max_length=128)

    def validate_email(self, value: str) -> str:
        normalized = value.strip().lower()
        if Teacher.objects.filter(email=normalized).exists():
            raise serializers.ValidationError("An account with this email exists.")
        return normalized

    def validate_full_name(self, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 2:
            raise serializers.ValidationError("Please enter your name.")
        return cleaned

    def validate(self, attrs: dict) -> dict:
        candidate = Teacher(
            email=attrs["email"],
            full_name=attrs["full_name"],
        )
        try:
            password_validation.validate_password(attrs["password"], candidate)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)}) from exc
        return attrs

    def create(self, validated_data: dict) -> Teacher:
        return Teacher.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            full_name=validated_data["full_name"],
            school_name=validated_data.get("school_name", ""),
        )


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(write_only=True, max_length=128)

    def validate(self, attrs: dict) -> dict:
        request = self.context.get("request")
        teacher = authenticate(
            request,
            username=attrs["email"].strip().lower(),
            password=attrs["password"],
        )
        if teacher is None:
            # Deliberately identical message for unknown email and wrong
            # password so the endpoint is not an account-existence oracle.
            raise serializers.ValidationError({"detail": "Incorrect email or password."})
        attrs["teacher"] = teacher
        return attrs
