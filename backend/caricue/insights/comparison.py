"""Session-over-session comparison for the adapt loop."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from django.db.models import Prefetch

from caricue.insights.service import build_session_insights
from caricue.insights.topics import topic_for_session
from caricue.live.models import IdentityMode, LiveSession, PlanImpact, SessionStatus


@dataclass
class BaselineSnapshot:
    session_id: int
    session_code: str
    closed_at: str | None
    overall_correctness: float | None
    primary_gap: str
    planned_action: str


@dataclass
class QuestionDelta:
    source_question_id: int | None
    baseline_position: int
    current_position: int
    baseline_correctness: float | None
    current_correctness: float | None
    delta: float | None


@dataclass
class StudentMovement:
    improved: list[dict] = field(default_factory=list)
    still_stuck: list[dict] = field(default_factory=list)
    improved_count: int = 0
    still_stuck_count: int = 0


@dataclass
class SessionComparison:
    kind: str = "fact"
    baseline_snapshot: BaselineSnapshot | None = None
    overall_delta: float | None = None
    question_deltas: list[QuestionDelta] = field(default_factory=list)
    alignment: str = "full"
    student_movement: StudentMovement | None = None
    tracking_mode: str = "class_only"

    def as_dict(self) -> dict:
        payload = asdict(self)
        if self.baseline_snapshot:
            payload["baseline_snapshot"] = asdict(self.baseline_snapshot)
        if self.student_movement:
            payload["student_movement"] = asdict(self.student_movement)
        return payload


def find_baseline_session(session: LiveSession) -> LiveSession | None:
    """Pick the prior session to compare against."""
    activity = session.activity
    if activity.follow_up_of_session_id:
        baseline = activity.follow_up_of_session
        if baseline and baseline.status == SessionStatus.CLOSED:
            return baseline

    topic = topic_for_session(session)
    if not topic or session.closed_at is None:
        return None

    candidates = (
        LiveSession.objects.filter(
            classroom=session.classroom,
            status=SessionStatus.CLOSED,
            closed_at__lt=session.closed_at,
        )
        .select_related("activity", "reflection")
        .prefetch_related("activity__questions")
    )

    matching = [
        s
        for s in candidates
        if topic_for_session(s) == topic and s.pk != session.pk
    ]
    if not matching:
        return None

    changed = [
        s
        for s in matching
        if getattr(s, "reflection", None)
        and s.reflection.plan_impact == PlanImpact.CHANGED
    ]
    pool = changed if changed else matching
    return max(pool, key=lambda s: s.closed_at or s.started_at)


def build_session_comparison(
    current: LiveSession, baseline: LiveSession | None = None
) -> SessionComparison | None:
    """Compare current session to a baseline; returns None if no baseline."""
    if baseline is None:
        baseline = find_baseline_session(current)
    if baseline is None:
        return None
    if current.status != SessionStatus.CLOSED:
        return None

    current_insights = build_session_insights(current)
    baseline_insights = build_session_insights(baseline)

    reflection = getattr(baseline, "reflection", None)
    baseline_snapshot = BaselineSnapshot(
        session_id=baseline.pk,
        session_code=baseline.code,
        closed_at=baseline.closed_at.isoformat() if baseline.closed_at else None,
        overall_correctness=baseline_insights.overall_correctness_percentage,
        primary_gap=reflection.primary_gap if reflection else "",
        planned_action=reflection.planned_action if reflection else "",
    )

    overall_delta = None
    if (
        current_insights.overall_correctness_percentage is not None
        and baseline_insights.overall_correctness_percentage is not None
    ):
        overall_delta = round(
            current_insights.overall_correctness_percentage
            - baseline_insights.overall_correctness_percentage,
            1,
        )

    question_deltas, alignment = _align_question_deltas(current, baseline)

    tracking_mode = "class_only"
    student_movement = None
    if (
        current.identity_mode == IdentityMode.ROSTER_IDENTIFIER
        and baseline.identity_mode == IdentityMode.ROSTER_IDENTIFIER
    ):
        tracking_mode = "roster"
        student_movement = _student_movement(
            current, baseline, baseline_insights, question_deltas
        )

    return SessionComparison(
        baseline_snapshot=baseline_snapshot,
        overall_delta=overall_delta,
        question_deltas=question_deltas,
        alignment=alignment,
        student_movement=student_movement,
        tracking_mode=tracking_mode,
    )


def _align_question_deltas(
    current: LiveSession, baseline: LiveSession
) -> tuple[list[QuestionDelta], str]:
    current_questions = list(
        current.activity.questions.order_by("position").values(
            "id", "position", "question_type", "source_question_id"
        )
    )
    baseline_questions = list(
        baseline.activity.questions.order_by("position").values(
            "id", "position", "question_type"
        )
    )

    current_insights = {
        q.question_id: q
        for q in build_session_insights(current).questions
    }
    baseline_insights = {
        q.question_id: q
        for q in build_session_insights(baseline).questions
    }

    deltas: list[QuestionDelta] = []
    has_lineage = any(q["source_question_id"] for q in current_questions)

    if has_lineage:
        for cq in current_questions:
            source_id = cq["source_question_id"]
            if not source_id:
                continue
            bq = next(
                (q for q in baseline_questions if q["id"] == source_id), None
            )
            if bq is None:
                continue
            b_ins = baseline_insights.get(source_id)
            c_ins = current_insights.get(cq["id"])
            delta = _correctness_delta(b_ins, c_ins)
            deltas.append(
                QuestionDelta(
                    source_question_id=source_id,
                    baseline_position=bq["position"],
                    current_position=cq["position"],
                    baseline_correctness=(
                        b_ins.correctness_percentage if b_ins else None
                    ),
                    current_correctness=(
                        c_ins.correctness_percentage if c_ins else None
                    ),
                    delta=delta,
                )
            )
        alignment = "full" if deltas else "partial"
        return deltas, alignment

    if len(current_questions) == len(baseline_questions) and all(
        cq["question_type"] == bq["question_type"]
        for cq, bq in zip(current_questions, baseline_questions, strict=True)
    ):
        for cq, bq in zip(current_questions, baseline_questions, strict=True):
            b_ins = baseline_insights.get(bq["id"])
            c_ins = current_insights.get(cq["id"])
            delta = _correctness_delta(b_ins, c_ins)
            deltas.append(
                QuestionDelta(
                    source_question_id=bq["id"],
                    baseline_position=bq["position"],
                    current_position=cq["position"],
                    baseline_correctness=(
                        b_ins.correctness_percentage if b_ins else None
                    ),
                    current_correctness=(
                        c_ins.correctness_percentage if c_ins else None
                    ),
                    delta=delta,
                )
            )
        return deltas, "full"

    return deltas, "partial"


def _correctness_delta(b_ins, c_ins) -> float | None:
    if (
        b_ins is None
        or c_ins is None
        or b_ins.correctness_percentage is None
        or c_ins.correctness_percentage is None
    ):
        return None
    return round(c_ins.correctness_percentage - b_ins.correctness_percentage, 1)


def _student_movement(
    current: LiveSession,
    baseline: LiveSession,
    baseline_insights,
    question_deltas: list[QuestionDelta],
) -> StudentMovement:
    focus_question_id = _weakest_question_id(baseline_insights)
    aligned_current_q = None
    for qd in question_deltas:
        if qd.source_question_id == focus_question_id:
            aligned_current_q = qd.current_position
            break

    baseline_participants = {
        p.student_id: p
        for p in baseline.participants.filter(student_id__isnull=False).prefetch_related(
            Prefetch("responses")
        )
    }
    current_participants = {
        p.student_id: p
        for p in current.participants.filter(student_id__isnull=False).prefetch_related(
            Prefetch("responses")
        )
    }

    common_ids = set(baseline_participants) & set(current_participants)
    improved: list[dict] = []
    still_stuck: list[dict] = []

    baseline_questions = {
        q.position: q.pk
        for q in baseline.activity.questions.all()
        if q.is_auto_scored
    }
    current_questions = {
        q.position: q.pk
        for q in current.activity.questions.all()
        if q.is_auto_scored
    }

    for student_id in common_ids:
        bp = baseline_participants[student_id]
        cp = current_participants[student_id]
        label = cp.label

        if focus_question_id and aligned_current_q:
            b_pos = next(
                (
                    qd.baseline_position
                    for qd in question_deltas
                    if qd.source_question_id == focus_question_id
                ),
                None,
            )
            if b_pos:
                b_qid = baseline_questions.get(b_pos)
                c_qid = current_questions.get(aligned_current_q)
                b_wrong = _response_incorrect(bp, b_qid)
                c_correct = _response_correct(cp, c_qid)
                b_stuck = _response_incorrect(bp, b_qid) and _response_incorrect(
                    cp, c_qid
                )
                if b_wrong and c_correct:
                    improved.append({"student_id": student_id, "label": label})
                elif b_stuck:
                    still_stuck.append({"student_id": student_id, "label": label})
                continue

        b_score = _auto_score_pct(bp)
        c_score = _auto_score_pct(cp)
        if b_score is not None and c_score is not None:
            if b_score < 50 and c_score >= 50:
                improved.append({"student_id": student_id, "label": label})
            elif b_score < 50 and c_score < 50:
                still_stuck.append({"student_id": student_id, "label": label})

    return StudentMovement(
        improved=improved[:10],
        still_stuck=still_stuck[:10],
        improved_count=len(improved),
        still_stuck_count=len(still_stuck),
    )


def _weakest_question_id(baseline_insights) -> int | None:
    scored = [
        q
        for q in baseline_insights.questions
        if q.correctness_percentage is not None and q.response_count > 0
    ]
    if not scored:
        return None
    weakest = min(scored, key=lambda q: (q.correctness_percentage, q.position))
    return weakest.question_id


def _response_incorrect(participant, question_id: int | None) -> bool:
    if question_id is None:
        return False
    for response in participant.responses.all():
        if response.question_id == question_id:
            return response.is_correct is False
    return False


def _response_correct(participant, question_id: int | None) -> bool:
    if question_id is None:
        return False
    for response in participant.responses.all():
        if response.question_id == question_id:
            return response.is_correct is True
    return False


def _auto_score_pct(participant) -> float | None:
    scored = [r for r in participant.responses.all() if r.is_correct is not None]
    if not scored:
        return None
    correct = sum(1 for r in scored if r.is_correct)
    return round(correct * 100 / len(scored), 1)


def build_topic_timeline(classroom) -> list[dict]:
    """Group closed sessions by normalised topic for a classroom."""
    sessions = (
        LiveSession.objects.filter(
            classroom=classroom,
            status=SessionStatus.CLOSED,
        )
        .select_related("activity", "reflection")
        .order_by("closed_at")
    )

    groups: dict[str, list[dict]] = {}
    for session in sessions:
        topic = topic_for_session(session)
        if not topic:
            topic = "(untitled)"
        insights = build_session_insights(session)
        reflection = getattr(session, "reflection", None)
        entry = {
            "id": session.pk,
            "code": session.code,
            "closed_at": session.closed_at.isoformat() if session.closed_at else None,
            "correctness": insights.overall_correctness_percentage,
            "has_reflection": reflection is not None,
            "plan_impact": reflection.plan_impact if reflection else None,
        }
        groups.setdefault(topic, []).append(entry)

    return [
        {"topic": topic, "sessions": items}
        for topic, items in sorted(groups.items(), key=lambda x: x[0])
    ]
