"""Give every existing class its own unique invite token."""

import secrets

from django.db import migrations


def populate_invite_tokens(apps, schema_editor):
    Classroom = apps.get_model("classroom", "Classroom")
    used: set[str] = set()
    for classroom in Classroom.objects.all().only("pk", "invite_token"):
        token = secrets.token_hex(16)
        while token in used:
            token = secrets.token_hex(16)
        used.add(token)
        Classroom.objects.filter(pk=classroom.pk).update(invite_token=token)


class Migration(migrations.Migration):

    dependencies = [
        ("classroom", "0002_class_invite"),
    ]

    operations = [
        migrations.RunPython(populate_invite_tokens, migrations.RunPython.noop),
    ]
