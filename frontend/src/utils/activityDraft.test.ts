import { describe, expect, it } from 'vitest';
import type { Question } from '@/api/types';
import {
  DEFAULT_LIMITS,
  blankQuestion,
  changeQuestionType,
  convertQuestionsForKind,
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
    expect(blankQuestion('rating', 'survey').choices).toHaveLength(0);
  });

  it('starts a multi-select with two empty choices and no answer key', () => {
    const question = blankQuestion('multi_select', 'survey');
    expect(question.choices).toHaveLength(2);
    expect(question.choices.every((choice) => !choice.is_correct)).toBe(true);
    expect(question.collect_confidence).toBe(false);
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

  it('keeps typed choices when switching between single and multi-select', () => {
    const switched = changeQuestionType(mcq(), 'multi_select');
    expect(switched.choices.map((c) => c.text)).toEqual(['Router', 'Switch']);
    expect(switched.choices.every((c) => !c.is_correct)).toBe(true);
  });
});

describe('convertQuestionsForKind', () => {
  it('turns a quiz confidence item into a rating when switching to a survey', () => {
    const [converted] = convertQuestionsForKind(
      [{ ...blankQuestion('confidence'), prompt: 'How sure?' }],
      'survey'
    );
    expect(converted.question_type).toBe('rating');
    expect(converted.collect_confidence).toBe(false);
  });

  it('strips the answer key so a survey cannot stay marked', () => {
    const [converted] = convertQuestionsForKind([mcq()], 'survey');
    expect(converted.choices.every((choice) => !choice.is_correct)).toBe(true);
    expect(converted.accepted_answers).toEqual([]);
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

  it('does not require an answer key on a survey choice question', () => {
    const question = mcq({
      choices: [
        { text: 'Cabling', is_correct: false },
        { text: 'Wi-Fi', is_correct: false },
      ],
    });
    expect(validateQuestion(question, DEFAULT_LIMITS, 'survey')).toBeNull();
  });

  it('requires two choices on a multi-select', () => {
    const question = {
      ...blankQuestion('multi_select', 'survey'),
      prompt: 'Which topics helped?',
      choices: [{ text: 'Only', is_correct: false }],
    };
    expect(validateQuestion(question, DEFAULT_LIMITS, 'survey')).toBe(
      'Multi-select questions need at least two choices.'
    );
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

  it('caps the activity at the limit the server publishes', () => {
    const limits = { ...DEFAULT_LIMITS, maxQuestions: 3 };
    const questions = Array.from({ length: 4 }, () => mcq());
    const errors = validateDraft({ title: 'Check', classroom: 1, questions }, limits);
    expect(errors.questions).toBe('An activity can have at most 3 questions.');
  });

  it('accepts far more than five questions by default', () => {
    const questions = Array.from({ length: 40 }, () => mcq());
    const errors = validateDraft({ title: 'Check', classroom: 1, questions });
    expect(errors.questions).toBeUndefined();
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

  it('keeps ids so the server can update saved questions and choices in place', () => {
    const payload = toWritePayload({
      title: 'Check',
      classroom: 1,
      questions: [
        mcq({
          id: 9,
          choices: [
            { id: 31, text: 'Router', is_correct: true },
            { text: 'Switch', is_correct: false },
          ],
        }),
      ],
    });
    expect(payload[0].id).toBe(9);
    expect(payload[0].choices).toEqual([
      { id: 31, text: 'Router', is_correct: true },
      { text: 'Switch', is_correct: false },
    ]);
  });

  it('omits positions, which the server assigns', () => {
    const payload = toWritePayload({ title: 'Check', classroom: 1, questions: [mcq()] });
    expect(payload[0]).not.toHaveProperty('position');
  });

  it('clears the answer key when the draft is a survey', () => {
    const payload = toWritePayload({
      title: 'Feedback',
      classroom: 1,
      kind: 'survey',
      questions: [mcq()],
    });
    expect(payload[0].choices.every((choice) => !choice.is_correct)).toBe(true);
    expect(payload[0].collect_confidence).toBe(false);
  });

  it('sends rating labels only on rating questions', () => {
    const payload = toWritePayload({
      title: 'Feedback',
      classroom: 1,
      kind: 'survey',
      questions: [
        {
          ...blankQuestion('rating', 'survey'),
          prompt: 'Pace?',
          rating_low_label: 'Too slow',
          rating_high_label: 'Too fast',
        },
      ],
    });
    expect(payload[0].rating_low_label).toBe('Too slow');
    expect(payload[0].rating_high_label).toBe('Too fast');
  });
});
