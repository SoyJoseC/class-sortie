"""Class invite token and self-enrollment toggle.

The token is added as nullable and non-unique here, populated per row in 0003,
and made unique in 0004. Adding a unique column with a callable default in one
step gives every existing row the *same* value (Django evaluates the default
once), which breaks the unique index on any database that already has classes.
"""

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
            field=models.CharField(max_length=64, null=True),
        ),
    ]
