"""Replay closed quiz sessions to rebuild the class-level review cards."""

from __future__ import annotations

from django.core.management.base import BaseCommand

from caricue.accounts.models import Teacher
from caricue.reviews.schedule import rebuild_schedule


class Command(BaseCommand):
    help = "Rebuild review cards by replaying closed quiz sessions in order."

    def add_arguments(self, parser):
        parser.add_argument(
            "--email",
            help="Limit the rebuild to one teacher's classes.",
        )

    def handle(self, *args, **options):
        teacher = None
        email = options.get("email")
        if email:
            teacher = Teacher.objects.filter(email__iexact=email).first()
            if teacher is None:
                self.stderr.write(f"No teacher with email {email}.")
                return
        count = rebuild_schedule(teacher=teacher)
        self.stdout.write(f"Applied {count} closed session(s) to the review schedule.")
