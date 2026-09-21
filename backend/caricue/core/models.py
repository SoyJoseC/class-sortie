from django.db import models


class TimeStampedModel(models.Model):
    """Adds `created_at` / `updated_at` to a model."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
