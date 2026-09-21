import type { Question, QuestionType } from '@/api/types';

/**
 * Client-side rules for the activity builder.
 *
 * These mirror the server's validation so the teacher gets immediate feedback
 * instead of a round trip. The server remains the authority: nothing here is
 * a security control.
 */

export const MIN_QUESTIONS = 1;
export const MAX_QUESTIONS = 5;
export const MAX_CHOICES = 6;

export function blankChoice(): { text: string; is_correct: boolean } {
  return { text: '', is_correct: false };
}

export function blankQuestion(type: QuestionType = 'multiple_choice'): Question {
  return {
    prompt: '',
    question_type: type,
    is_required: true,
    collect_confidence: type === 'multiple_choice',
    accepted_answers: [],
    choices: type === 'multiple_choice' ? [blankChoice(), blankChoice()] : [],
  };
}

/**
 * Rewrites a question when its type changes, dropping fields that no longer
 * apply so a stale answer key cannot survive a type switch.
 */
export function changeQuestionType(question: Question, type: QuestionType): Question {
  if (type === question.question_type) return question;
  return {
    ...question,
    question_type: type,
    choices: type === 'multiple_choice' ? [blankChoice(), blankChoice()] : [],
    accepted_answers: type === 'short_text' ? question.accepted_answers : [],
    collect_confidence: type === 'confidence' ? false : question.collect_confidence,
  };
}

export function moveQuestion(questions: Question[], from: number, to: number): Question[] {
  if (from === to || from < 0 || to < 0 || from >= questions.length || to >= questions.length) {
    return questions;
  }
  const next = [...questions];
  const [moved] = next.splice(from, 1);
  next.splice(to, 0, moved);
  return next;
}

export interface DraftErrors {
  title?: string;
  classroom?: string;
  questions?: string;
  /** Keyed by question index. */
  byQuestion: Record<number, string>;
}

export interface DraftInput {
  title: string;
  classroom: number | null;
  questions: Question[];
}

/** Validates a draft. An empty `byQuestion` and no top-level keys means valid. */
export function validateDraft(draft: DraftInput): DraftErrors {
  const errors: DraftErrors = { byQuestion: {} };

  if (!draft.title.trim()) errors.title = 'Give the activity a title.';
  if (!draft.classroom) errors.classroom = 'Choose the class this is for.';

  if (draft.questions.length < MIN_QUESTIONS) {
    errors.questions = `Add at least ${MIN_QUESTIONS} question.`;
  } else if (draft.questions.length > MAX_QUESTIONS) {
    errors.questions = `An activity can have at most ${MAX_QUESTIONS} questions.`;
  }

  draft.questions.forEach((question, index) => {
    const problem = validateQuestion(question);
    if (problem) errors.byQuestion[index] = problem;
  });

  return errors;
}

export function validateQuestion(question: Question): string | null {
  if (!question.prompt.trim()) return 'Enter the question prompt.';

  if (question.question_type === 'multiple_choice') {
    const filled = question.choices.filter((choice) => choice.text.trim().length > 0);
    if (filled.length < 2) return 'Multiple-choice questions need at least two choices.';
    if (filled.length > MAX_CHOICES) return `At most ${MAX_CHOICES} choices.`;
    if (!filled.some((choice) => choice.is_correct)) return 'Mark at least one choice correct.';

    const seen = new Set<string>();
    for (const choice of filled) {
      const key = choice.text.trim().toLowerCase();
      if (seen.has(key)) return 'Choices must be different from each other.';
      seen.add(key);
    }
    // A choice marked correct but left blank would silently vanish on save.
    if (question.choices.some((c) => c.is_correct && !c.text.trim())) {
      return 'A choice marked correct has no text.';
    }
  }

  return null;
}

export function isDraftValid(errors: DraftErrors): boolean {
  return (
    !errors.title &&
    !errors.classroom &&
    !errors.questions &&
    Object.keys(errors.byQuestion).length === 0
  );
}

/** Parses the accepted-answers textarea: one answer per line. */
export function parseAcceptedAnswers(raw: string): string[] {
  const seen = new Set<string>();
  const result: string[] = [];
  for (const line of raw.split('\n')) {
    const text = line.trim();
    if (!text) continue;
    // Dedupe using the same normalisation the server applies.
    const key = text.replace(/\s+/g, ' ').toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    result.push(text);
  }
  return result;
}

export function formatAcceptedAnswers(answers: string[]): string {
  return answers.join('\n');
}

/**
 * Strips empty choices and normalises whitespace, producing the payload the
 * API expects. Positions are assigned by the server.
 */
export function toWritePayload(draft: DraftInput): Question[] {
  return draft.questions.map((question) => ({
    prompt: question.prompt.trim(),
    question_type: question.question_type,
    is_required: question.is_required,
    collect_confidence:
      question.question_type === 'confidence' ? false : question.collect_confidence,
    accepted_answers: question.question_type === 'short_text' ? question.accepted_answers : [],
    choices:
      question.question_type === 'multiple_choice'
        ? question.choices
            .filter((choice) => choice.text.trim().length > 0)
            .map((choice) => ({ text: choice.text.trim(), is_correct: choice.is_correct }))
        : [],
  }));
}
