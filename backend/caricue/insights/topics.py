"""Topic normalisation for grouping sessions and finding baselines."""

from __future__ import annotations

from caricue.activities.models import normalize_text_answer
from caricue.live.models import LiveSession


def normalize_topic(text: str | None) -> str:
    """Normalise a topic string the same way short-text answers are compared."""
    return normalize_text_answer(text or "")


def topic_for_session(session: LiveSession) -> str:
    """Stable topic key for a session — topic label, falling back to title."""
    activity = session.activity
    return normalize_topic(activity.topic or activity.title)
