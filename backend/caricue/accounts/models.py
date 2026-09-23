"""The teacher account model.

CariCue has exactly one authenticated actor: a teacher. Rather than bolting a
profile onto `auth.User`, the project ships a custom user keyed on email so
there is no vestigial username field and no ambiguity about who owns data.
Students never get accounts.
"""

from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone

from caricue.core.models import TimeStampedModel


class TeacherManager(BaseUserManager):
    use_in_migrations = True

    def _create(self, email: str, password: str | None, **extra):
        if not email:
            raise ValueError("Teachers must have an email address.")
        email = self.normalize_email(email).strip().lower()
        teacher = self.model(email=email, **extra)
        teacher.set_password(password)
        teacher.full_clean(exclude=["password", "last_login"])
        teacher.save(using=self._db)
        return teacher

    def create_user(self, email: str, password: str | None = None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create(email, password, **extra)

    def create_superuser(self, email: str, password: str | None = None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        if not extra["is_staff"] or not extra["is_superuser"]:
            raise ValueError("Superusers must have is_staff and is_superuser set.")
        return self._create(email, password, **extra)


class Teacher(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True, max_length=254)
    full_name = models.CharField(max_length=150)
    school_name = models.CharField(max_length=150, blank=True)
    google_sub = models.CharField(
        max_length=255,
        blank=True,
        unique=True,
        null=True,
        help_text="Google account subject id when linked via OAuth.",
    )
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = TeacherManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        verbose_name = "teacher"
        verbose_name_plural = "teachers"
        ordering = ["email"]

    def __str__(self) -> str:
        return self.email

    def get_full_name(self) -> str:
        return self.full_name or self.email

    def get_short_name(self) -> str:
        return (self.full_name or self.email).split(" ")[0]

    @property
    def owner_teacher_id(self) -> int | None:
        return self.pk


class StudentAccount(TimeStampedModel):
    """A student who signed in with Google — distinct from roster `Student` rows."""

    email = models.EmailField(unique=True, max_length=254)
    full_name = models.CharField(max_length=150)
    google_sub = models.CharField(max_length=255, unique=True)

    class Meta:
        ordering = ["email"]

    def __str__(self) -> str:
        return self.email
