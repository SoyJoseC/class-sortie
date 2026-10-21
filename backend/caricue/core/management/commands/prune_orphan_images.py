"""Deletes question images that were uploaded but never attached to a question.

The builder uploads a picture the moment it is chosen, so abandoned drafts and
replaced pictures leave unattached rows behind. This removes the ones older
than a grace period (default 24 hours, long enough for a draft left open).

    python manage.py prune_orphan_images [--hours 24] [--dry-run]

Safe to run from cron.
"""

from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from caricue.activities.models import QuestionImage


class Command(BaseCommand):
    help = "Delete unattached question images older than the grace period."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--hours", type=int, default=24, help="Grace period in hours (default 24)."
        )
        parser.add_argument(
            "--dry-run", action="store_true", help="Report what would be deleted."
        )

    def handle(self, *args, **options) -> None:
        cutoff = timezone.now() - timedelta(hours=options["hours"])
        orphans = QuestionImage.objects.filter(
            questions__isnull=True, created_at__lt=cutoff
        )
        count = orphans.count()
        if options["dry_run"]:
            self.stdout.write(f"{count} orphan image(s) would be deleted.")
            return
        for image in orphans:
            image.file.delete(save=False)
            image.delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {count} orphan image(s)."))
