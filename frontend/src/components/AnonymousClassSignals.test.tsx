import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { AnonymousClassSignals } from './AnonymousClassSignals';
import type { SessionFacts } from '@/api/types';

function minimalFacts(
  overrides: Partial<SessionFacts> = {}
): SessionFacts {
  return {
    kind: 'fact',
    session_id: 1,
    session_code: 'ABC123',
    session_status: 'open',
    activity_title: 'Check',
    activity_topic: '',
    classroom_name: 'Form 4',
    roster_size: 0,
    participant_count: 5,
    submitted_count: 5,
    completion_percentage: 100,
    auto_scored_response_count: 5,
    overall_correctness_percentage: 60,
    confidence_distribution: {},
    average_confidence: 3,
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

describe('AnonymousClassSignals', () => {
  it('does not render student names', () => {
    render(
      <AnonymousClassSignals
        facts={minimalFacts({
          high_confidence_incorrect: [
            {
              participant_id: 1,
              label: 'Amara J',
              question_position: 2,
              question_prompt: 'What is RAM?',
              confidence_value: 5,
            },
            {
              participant_id: 2,
              label: 'Devon C',
              question_position: 2,
              question_prompt: 'What is RAM?',
              confidence_value: 4,
            },
          ],
        })}
      />
    );

    expect(screen.getByText(/2 responses/)).toBeInTheDocument();
    expect(screen.queryByText('Amara J')).not.toBeInTheDocument();
    expect(screen.queryByText('Devon C')).not.toBeInTheDocument();
  });
});
