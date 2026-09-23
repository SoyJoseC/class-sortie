"""StudentAccount model and Teacher.google_sub."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="teacher",
            name="google_sub",
            field=models.CharField(
                blank=True,
                help_text="Google account subject id when linked via OAuth.",
                max_length=255,
                null=True,
                unique=True,
            ),
        ),
        migrations.CreateModel(
            name="StudentAccount",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("email", models.EmailField(max_length=254, unique=True)),
                ("full_name", models.CharField(max_length=150)),
                ("google_sub", models.CharField(max_length=255, unique=True)),
            ],
            options={
                "ordering": ["email"],
            },
        ),
    ]
