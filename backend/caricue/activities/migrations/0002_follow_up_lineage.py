"""Follow-up activity and question lineage fields."""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("live", "0001_initial"),
        ("activities", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="activity",
            name="follow_up_of_session",
            field=models.ForeignKey(
                blank=True,
                help_text="Set when this draft was generated from a prior live session.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="follow_up_activities",
                to="live.livesession",
            ),
        ),
        migrations.AddField(
            model_name="question",
            name="source_question",
            field=models.ForeignKey(
                blank=True,
                help_text="Weak question this follow-up item targets.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="follow_up_questions",
                to="activities.question",
            ),
        ),
        migrations.AddField(
            model_name="question",
            name="source_session",
            field=models.ForeignKey(
                blank=True,
                help_text="Session that motivated this follow-up question.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="follow_up_questions",
                to="live.livesession",
            ),
        ),
    ]
