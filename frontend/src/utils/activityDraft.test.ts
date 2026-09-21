import { describe, expect, it } from 'vitest';
import type { Question } from '@/api/types';
import {
  MAX_QUESTIONS,
  blankQuestion,
  changeQuestionType,
  formatAcceptedAnswers,
  isDraftValid,
  moveQuestion,
  parseAcceptedAnswers,
  toWritePayload,
  validateDraft,
  validateQuestion,
} from './activityDraft';

function mcq(overrides: Partial<Question> = {}): Question {
  return {
    ...blankQuestion('multiple_choice'),
    prompt: 'Which device routes between networks?',
    choices: [
      { text: 'Router', is_correct: true },
      { text: 'Switch', is_correct: false },
    ],
    ...overrides,
  };
}

describe('blankQuestion', () => {
  it('starts a multiple-choice question with two empty choices', () => {
    const question = blankQuestion();
    expect(question.question_type).toBe('multiple_choice');
    expect(question.choices).toHaveLength(2);
    expect(question.is_required).toBe(true);
  });

  it('gives non-choice types no choices', () => {
    expect(blankQuestion('short_text').choices).toHaveLength(0);
    expect(blankQuestion('confidence').choices).toHaveLength(0);
  });
});

describe('changeQuestionType', () => {
  it('drops the answer key so a stale one cannot survive a type switch', () => {
    const switched = changeQuestionType(mcq(), 'short_text');
    expect(switched.choices).toHaveLength(0);
    expect(switched.question_type).toBe('short_text');
  });

  it('drops accepted answers when leaving short text', () => {
    const shortText: Question = {
      ...blankQuestion('short_text'),
      prompt: 'What does RAM stand for?',
      accepted_answers: ['Random Access Memory'],
    };
    expect(changeQuestionType(shortText, 'multiple_choice').accepted_answers).toEqual([]);
  });

  it('never asks for confidence twice on a confidence question', () => {
    const question = mcq({ collect_confidence: true });
    expect(changeQuestionType(question, 'confidence').collect_confidence).toBe(false);
  });

  it('returns the same object when the type has not changed', () => {
    const question = mcq();
    expect(changeQuestionType(question, 'multiple_choice')).toBe(question);
  });
});

describe('moveQuestion', () => {
  const questions = [mcq({ prompt: 'A' }), mcq({ prompt: 'B' }), mcq({ prompt: 'C' })];

  it('reorders questions', () => {
    expect(moveQuestion(questions, 0, 2).map((q) => q.prompt)).toEqual(['B', 'C', 'A']);
    expect(moveQuestion(questions, 2, 0).map((q) => q.prompt)).toEqual(['C', 'A', 'B']);
  });

  it('ignores out-of-range moves rather than dropping a question', () => {
    expect(moveQuestion(questions, 0, -1)).toBe(questions);
    expect(moveQuestion(questions, 0, 3)).toBe(questions);
    expect(moveQuestion(questions, 1, 1)).toBe(questions);
  });
});

describe('validateQuestion', () => {
  it('accepts a well-formed multiple-choice question', () => {
    expect(validateQuestion(mcq())).toBeNull();
  });

  it('requires a prompt', () => {
    expect(validateQuestion(mcq({ prompt: '   ' }))).toBe('Enter the question prompt.');
  });

  it('requires two usable choices', () => {
    const question = mcq({
      choices: [
        { text: 'Router', is_correct: true },
        { text: '   ', is_correct: false },
      ],
    });
    expect(validateQuestion(question)).toBe(
      'Multiple-choice questions need at least two choices.'
    );
  });

  it('requires a correct choice, because otherwise nothing can be scored', () => {
    const question = mcq({
      choices: [
        { text: 'Router', is_correct: false },
        { text: 'Switch', is_correct: false },
      ],
    });
    expect(validateQuestion(question)).toBe('Mark at least one choice correct.');
  });

  it('rejects duplicate choices regardless of case and spacing', () => {
    const question = mcq({
      choices: [
        { text: 'Router', is_correct: true },
        { text: 'router', is_correct: false },
      ],
    });
    expect(validateQuestion(question)).toBe('Choices must be different from each other.');
  });

  // A blank choice is stripped on save, so a correct-but-blank choice would
  // quietly produce an unscorable question.
  it('rejects a correct choice with no text', () => {
    const question = mcq({
      choices: [
        { text: 'Router', is_correct: true },
        { text: 'Switch', is_correct: false },
        { text: '', is_correct: true },
      ],
    });
    expect(validateQuestion(question)).toBe('A choice marked correct has no text.');
  });

  it('does not require an answer key for short text or confidence', () => {
    expect(
      validateQuestion({ ...blankQuestion('short_text'), prompt: 'Explain why.' })
    ).toBeNull();
    expect(
      validateQuestion({ ...blankQuestion('confidence'), prompt: 'How sure are you?' })
    ).toBeNull();
  });
});

describe('validateDraft', () => {
  it('accepts a complete draft', () => {
    const errors = validateDraft({
      title: 'Networking check',
      classroom: 3,
      questions: [mcq()],
    });
    expect(isDraftValid(errors)).toBe(true);
  });

  it('reports a missing title and class', () => {
    const errors = validateDraft({ title: '  ', classroom: null, questions: [mcq()] });
    expect(errors.title).toBe('Give the activity a title.');
    expect(errors.classroom).toBe('Choose the class this is for.');
    expect(isDraftValid(errors)).toBe(false);
  });

  it('requires at least one question', () => {
    const errors = validateDraft({ title: 'Check', classroom: 1, questions: [] });
    expect(errors.questions).toBe('Add at least 1 question.');
  });

  it('caps the activity at five questions to keep it a quick check', () => {
    const questions = Array.from({ length: MAX_QUESTIONS + 1 }, () => mcq());
    const errors = validateDraft({ title: 'Check', classroom: 1, questions });
    expect(errors.questions).toBe(`An activity can have at most ${MAX_QUESTIONS} questions.`);
  });

  it('keys question problems by index so the right card is highlighted', () => {
    const errors = validateDraft({
      title: 'Check',
      classroom: 1,
      questions: [mcq(), mcq({ prompt: '' })],
    });
    expect(errors.byQuestion[0]).toBeUndefined();
    expect(errors.byQuestion[1]).toBe('Enter the question prompt.');
    expect(isDraftValid(errors)).toBe(false);
  });
});

describe('accepted answers', () => {
  it('parses one answer per line, ignoring blanks', () => {
    expect(parseAcceptedAnswers('Random Access Memory\n\n  RAM  \n')).toEqual([
      'Random Access Memory',
      'RAM',
    ]);
  });

  it('dedupes using the same normalisation the server applies', () => {
    expect(parseAcceptedAnswers('RAM\nram\n  R A M  ')).toEqual(['RAM', 'R A M']);
  });

  it('round-trips back into the textarea', () => {
    const answers = ['Random Access Memory', 'RAM'];
    expect(parseAcceptedAnswers(formatAcceptedAnswers(answers))).toEqual(answers);
  });
});

describe('toWritePayload', () => {
  it('trims prompts and drops empty choices', () => {
    const payload = toWritePayload({
      title: 'Check',
      classroom: 1,
      questions: [
        mcq({
          prompt: '  Which device routes between networks?  ',
          choices: [
            { text: ' Router ', is_correct: true },
            { text: 'Switch', is_correct: false },
            { text: '   ', is_correct: false },
          ],
        }),
      ],
    });

    expect(payload[0].prompt).toBe('Which device routes between networks?');
    expect(payload[0].choices).toEqual([
      { text: 'Router', is_correct: true },
      { text: 'Switch', is_correct: false },
    ]);
  });

  it('sends no choices or accepted answers for types that cannot use them', () => {
    const payload = toWritePayload({
      title: 'Check',
      classroom: 1,
      questions: [
        { ...blankQuestion('confidence'), prompt: 'How sure?', accepted_answers: ['stale'] },
      ],
    });

    expect(payload[0].choices).toEqual([]);
    expect(payload[0].accepted_answers).toEqual([]);
    expect(payload[0].collect_confidence).toBe(false);
  });

  it('omits positions, which the server assigns', () => {
    const payload = toWritePayload({ title: 'Check', classroom: 1, questions: [mcq()] });
    expect(payload[0]).not.toHaveProperty('position');
  });
});
