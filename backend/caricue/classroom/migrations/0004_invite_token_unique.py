"""Make the invite token unique and required, now that every row has one."""

import caricue.classroom.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("classroom", "0003_populate_invite_tokens"),
    ]

    operations = [
        migrations.AlterField(
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
