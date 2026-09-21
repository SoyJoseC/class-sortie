import { describe, expect, it } from 'vitest';
import type { AttentionItem, QuestionInsight, SessionFacts } from '@/api/types';
import {
  NOT_AVAILABLE,
  confidenceBars,
  correctnessTone,
  describeAttention,
  describeCorrectness,
  formatCompletion,
  formatConfidence,
  formatDateTime,
  formatPercent,
  formatRelativeTime,
  formatSessionCode,
  hasPerformanceConfidenceSignal,
  questionTypeLabel,
  totalConfidenceResponses,
} from './insightFormat';

function questionInsight(overrides: Partial<QuestionInsight> = {}): QuestionInsight {
  return {
    question_id: 1,
    position: 1,
    prompt: 'Which device routes between networks?',
    question_type: 'multiple_choice',
    is_auto_scored: true,
    response_count: 4,
    correct_count: 3,
    incorrect_count: 1,
    correctness_percentage: 75,
    choice_breakdown: [],
    common_answers: [],
    confidence_distribution: {},
    average_confidence: null,
    ...overrides,
  };
}

function facts(overrides: Partial<SessionFacts> = {}): SessionFacts {
  return {
    kind: 'fact',
    session_id: 1,
    session_code: 'ABC123',
    session_status: 'open',
    activity_title: 'Networking check',
    activity_topic: 'Switches and routers',
    classroom_name: 'IT 4B',
    roster_size: 24,
    participant_count: 12,
    submitted_count: 12,
    completion_percentage: 50,
    auto_scored_response_count: 24,
    overall_correctness_percentage: 62.5,
    confidence_distribution: {},
    average_confidence: null,
    questions: [],
    lowest_correctness_questions: [],
    high_confidence_incorrect: [],
    low_confidence_correct: [],
    needs_attention: [],
    has_confidence_data: false,
    has_auto_scored_data: true,
    ...overrides,
  };
}

describe('formatPercent', () => {
  it('formats a number as a whole percentage by default', () => {
    expect(formatPercent(62.5)).toBe('63%');
    expect(formatPercent(0)).toBe('0%');
    expect(formatPercent(100)).toBe('100%');
  });

  it('honours a requested precision', () => {
    expect(formatPercent(62.46, 1)).toBe('62.5%');
  });

  // The distinction that matters to a teacher: "nobody got it right" is not
  // the same statement as "we cannot tell yet".
  it('shows a dash rather than a misleading zero when the value is unknown', () => {
    expect(formatPercent(null)).toBe(NOT_AVAILABLE);
    expect(formatPercent(undefined)).toBe(NOT_AVAILABLE);
    expect(formatPercent(Number.NaN)).toBe(NOT_AVAILABLE);
  });
});

describe('formatConfidence', () => {
  it('renders confidence out of five to one decimal', () => {
    expect(formatConfidence(3)).toBe('3.0 / 5');
    expect(formatConfidence(4.25)).toBe('4.3 / 5');
  });

  it('does not invent a value when none was collected', () => {
    expect(formatConfidence(null)).toBe(NOT_AVAILABLE);
  });
});

describe('formatCompletion', () => {
  it('reports against the roster when the roster size is known', () => {
    expect(formatCompletion({ submitted_count: 12, roster_size: 24 })).toBe(
      '12 of 24 students'
    );
  });

  it('singularises a roster of one', () => {
    expect(formatCompletion({ submitted_count: 1, roster_size: 1 })).toBe('1 of 1 student');
  });

  it('omits the denominator when there is no roster', () => {
    expect(formatCompletion({ submitted_count: 7, roster_size: 0 })).toBe('7 submitted');
  });
});

describe('describeCorrectness', () => {
  it('reports the score with the underlying counts', () => {
    expect(describeCorrectness(questionInsight())).toBe('75% correct (3/4)');
  });

  it('distinguishes an unanswered question from a zero score', () => {
    expect(
      describeCorrectness(
        questionInsight({ response_count: 0, correct_count: 0, incorrect_count: 0 })
      )
    ).toBe('No responses yet');
  });

  it('says so when a question cannot be auto-scored', () => {
    const shortText = questionInsight({
      question_type: 'short_text',
      is_auto_scored: false,
      correctness_percentage: null,
    });
    expect(describeCorrectness(shortText)).toBe('Not auto-scored — read the responses');
  });

  it('treats a null percentage on a scored question as unscorable', () => {
    expect(describeCorrectness(questionInsight({ correctness_percentage: null }))).toBe(
      'Not auto-scored — read the responses'
    );
  });
});

describe('correctnessTone', () => {
  it('maps scores to tones on the same thresholds as the backend', () => {
    expect(correctnessTone(95)).toBe('success');
    expect(correctnessTone(80)).toBe('success');
    expect(correctnessTone(79.9)).toBe('warning');
    expect(correctnessTone(60)).toBe('warning');
    expect(correctnessTone(59.9)).toBe('danger');
    expect(correctnessTone(0)).toBe('danger');
  });

  it('stays neutral when there is no score', () => {
    expect(correctnessTone(null)).toBe('neutral');
  });
});

describe('confidenceBars', () => {
  it('always returns five ordered levels, including empty ones', () => {
    const bars = confidenceBars({ '1': 1, '5': 3 });
    expect(bars.map((bar) => bar.level)).toEqual([1, 2, 3, 4, 5]);
    expect(bars.map((bar) => bar.count)).toEqual([1, 0, 0, 0, 3]);
    expect(bars[0].percentage).toBe(25);
    expect(bars[4].percentage).toBe(75);
  });

  it('reports zero percentages instead of dividing by zero', () => {
    const bars = confidenceBars(undefined);
    expect(bars).toHaveLength(5);
    expect(bars.every((bar) => bar.count === 0 && bar.percentage === 0)).toBe(true);
  });

  it('totals the responses across levels', () => {
    expect(totalConfidenceResponses({ '2': 2, '4': 5 })).toBe(7);
    expect(totalConfidenceResponses(undefined)).toBe(0);
  });
});

describe('hasPerformanceConfidenceSignal', () => {
  it('requires confidence data, scored data, and at least one signal', () => {
    const signal = {
      participant_id: 1,
      label: 'Amara J.',
      question_position: 2,
      question_prompt: 'Which device?',
      confidence_value: 5,
    };
    expect(
      hasPerformanceConfidenceSignal(
        facts({ has_confidence_data: true, high_confidence_incorrect: [signal] })
      )
    ).toBe(true);
  });

  it('stays hidden when there is nothing to conclude', () => {
    expect(hasPerformanceConfidenceSignal(facts({ has_confidence_data: true }))).toBe(false);
    expect(hasPerformanceConfidenceSignal(facts({ has_auto_scored_data: false }))).toBe(false);
  });
});

describe('describeAttention', () => {
  it('joins the reasons into one readable line', () => {
    const item: AttentionItem = {
      participant_id: 3,
      label: 'Kemar B.',
      reasons: ['Scored 25% on auto-scored questions', 'Confident but incorrect on Q2'],
      score_percentage: 25,
      average_confidence: 4.5,
    };
    expect(describeAttention(item)).toBe(
      'Scored 25% on auto-scored questions · Confident but incorrect on Q2'
    );
  });
});

describe('formatSessionCode', () => {
  it('splits a six-character code so it can be read aloud', () => {
    expect(formatSessionCode('ABC123')).toBe('ABC 123');
  });

  it('leaves unexpected lengths untouched', () => {
    expect(formatSessionCode('AB12')).toBe('AB12');
  });
});

describe('formatRelativeTime', () => {
  const now = new Date('2026-03-04T10:00:00Z').getTime();

  it('describes recent updates in the units a teacher cares about', () => {
    expect(formatRelativeTime('2026-03-04T09:59:58Z', now)).toBe('just now');
    expect(formatRelativeTime('2026-03-04T09:59:30Z', now)).toBe('30s ago');
    expect(formatRelativeTime('2026-03-04T09:45:00Z', now)).toBe('15m ago');
    expect(formatRelativeTime('2026-03-04T07:00:00Z', now)).toBe('3h ago');
    expect(formatRelativeTime('2026-03-01T10:00:00Z', now)).toBe('3d ago');
  });

  it('handles missing and unparseable timestamps', () => {
    expect(formatRelativeTime(null, now)).toBe(NOT_AVAILABLE);
    expect(formatRelativeTime('not a date', now)).toBe(NOT_AVAILABLE);
  });
});

describe('formatDateTime', () => {
  it('returns a dash for missing or invalid input', () => {
    expect(formatDateTime(null)).toBe(NOT_AVAILABLE);
    expect(formatDateTime('nonsense')).toBe(NOT_AVAILABLE);
  });

  it('renders a real timestamp', () => {
    expect(formatDateTime('2026-03-04T10:00:00Z')).toContain('2026');
  });
});

describe('questionTypeLabel', () => {
  it('labels every supported question type', () => {
    expect(questionTypeLabel('multiple_choice')).toBe('Multiple choice');
    expect(questionTypeLabel('short_text')).toBe('Short text');
    expect(questionTypeLabel('confidence')).toBe('Confidence 1-5');
  });
});
