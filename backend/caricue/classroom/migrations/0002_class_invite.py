"""Class invite token and self-enrollment toggle."""

import caricue.classroom.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("classroom", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="classroom",
            name="self_enrollment_enabled",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "When enabled, students may join via the class QR with Google sign-in."
                ),
            ),
        ),
        migrations.AddField(
            model_name="classroom",
            name="invite_token",
            field=models.CharField(
                db_index=True,
                default=caricue.classroom.models.generate_invite_token,
                max_length=64,
                unique=True,
            ),
        ),
    ]
