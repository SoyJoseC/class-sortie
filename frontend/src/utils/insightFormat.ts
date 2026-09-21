import type {
  AttentionItem,
  ConfidenceDistribution,
  QuestionInsight,
  QuestionType,
  SessionFacts,
} from '@/api/types';

/**
 * Formatting helpers for the results screens.
 *
 * The rule these all follow: when a figure cannot honestly be computed, say
 * so rather than printing a misleading zero. "0% correct" and "no scored
 * answers yet" mean very different things to a teacher deciding what to
 * reteach.
 */

export const NOT_AVAILABLE = '—';

/** A percentage, or a dash when the value is genuinely unknown. */
export function formatPercent(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return NOT_AVAILABLE;
  return `${value.toFixed(digits)}%`;
}

export function formatConfidence(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return NOT_AVAILABLE;
  return `${value.toFixed(1)} / 5`;
}

/** "12 of 24 students" / "12 submitted" when the roster size is unknown. */
export function formatCompletion(
  facts: Pick<SessionFacts, 'submitted_count' | 'roster_size'>
): string {
  const { submitted_count: submitted, roster_size: roster } = facts;
  if (roster > 0) {
    return `${submitted} of ${roster} student${roster === 1 ? '' : 's'}`;
  }
  return `${submitted} submitted`;
}

export const QUESTION_TYPE_LABELS: Record<QuestionType, string> = {
  multiple_choice: 'Multiple choice',
  short_text: 'Short text',
  confidence: 'Confidence 1-5',
};

export function questionTypeLabel(type: QuestionType): string {
  return QUESTION_TYPE_LABELS[type] ?? type;
}

/**
 * Correctness as a sentence, distinguishing "not scorable" from "nobody has
 * answered yet" from an actual score.
 */
export function describeCorrectness(question: QuestionInsight): string {
  if (!question.is_auto_scored) return 'Not auto-scored — read the responses';
  if (question.response_count === 0) return 'No responses yet';
  if (question.correctness_percentage === null) return 'Not auto-scored — read the responses';
  return `${formatPercent(question.correctness_percentage)} correct (${question.correct_count}/${
    question.correct_count + question.incorrect_count
  })`;
}

export type ToneName = 'success' | 'warning' | 'danger' | 'neutral';

/** Maps a correctness score to a colour tone. Thresholds match the backend. */
export function correctnessTone(value: number | null | undefined): ToneName {
  if (value === null || value === undefined) return 'neutral';
  if (value >= 80) return 'success';
  if (value >= 60) return 'warning';
  return 'danger';
}

export const TONE_COLOR_SCHEMES: Record<ToneName, string> = {
  success: 'cariteal',
  warning: 'yellow',
  danger: 'coral',
  neutral: 'gray',
};

export function toneColorScheme(tone: ToneName): string {
  return TONE_COLOR_SCHEMES[tone];
}

export interface ConfidenceBar {
  level: number;
  count: number;
  percentage: number;
}

/**
 * Normalises the 1-5 confidence map into a stable, ordered array so the chart
 * always renders five bars even when a level has no responses.
 */
export function confidenceBars(
  distribution: ConfidenceDistribution | undefined
): ConfidenceBar[] {
  const levels = [1, 2, 3, 4, 5];
  const counts = levels.map((level) => distribution?.[String(level)] ?? 0);
  const total = counts.reduce((sum, count) => sum + count, 0);
  return levels.map((level, index) => ({
    level,
    count: counts[index],
    percentage: total === 0 ? 0 : Math.round((counts[index] / total) * 1000) / 10,
  }));
}

export function totalConfidenceResponses(
  distribution: ConfidenceDistribution | undefined
): number {
  return confidenceBars(distribution).reduce((sum, bar) => sum + bar.count, 0);
}

/** One-line summary of a participant's reasons for needing attention. */
export function describeAttention(item: AttentionItem): string {
  return item.reasons.join(' · ');
}

/**
 * Student-facing wording for the 1-5 scale, also used as the accessible name
 * of each radio. Each label is distinct enough to be read on its own.
 */
const CONFIDENCE_WORDS: Record<number, string> = {
  1: 'Guessing',
  2: 'A little unsure',
  3: 'Somewhat sure',
  4: 'Fairly sure',
  5: 'Very sure',
};

export function confidenceLabel(level: number): string {
  return CONFIDENCE_WORDS[level] ?? `Level ${level}`;
}

/**
 * Whether there is enough evidence to talk about performance versus
 * confidence. Below this bar the dashboard hides the panel instead of
 * drawing conclusions from one or two answers.
 */
export function hasPerformanceConfidenceSignal(facts: SessionFacts): boolean {
  return (
    facts.has_confidence_data &&
    facts.has_auto_scored_data &&
    facts.high_confidence_incorrect.length + facts.low_confidence_correct.length > 0
  );
}

/** Short, human relative time for "last updated" indicators. */
export function formatRelativeTime(iso: string | null | undefined, now = Date.now()): string {
  if (!iso) return NOT_AVAILABLE;
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return NOT_AVAILABLE;
  const seconds = Math.round((now - then) / 1000);
  if (seconds < 5) return 'just now';
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return NOT_AVAILABLE;
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return NOT_AVAILABLE;
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/** Formats a short code as "ABC DEF" so it is easier to read aloud. */
export function formatSessionCode(code: string): string {
  if (code.length !== 6) return code;
  return `${code.slice(0, 3)} ${code.slice(3)}`;
}
