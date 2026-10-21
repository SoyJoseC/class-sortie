import type { ActivityKind, Choice, Question, QuestionType } from '@/api/types';

/**
 * Client-side rules for the activity builder.
 *
 * These mirror the server's validation so the teacher gets immediate feedback
 * instead of a round trip. The server remains the authority: nothing here is
 * a security control.
 */

export interface ActivityLimits {
  minQuestions: number;
  maxQuestions: number;
  maxChoices: number;
}

/**
 * Used until `/api/config/` answers. The server publishes the real limits and
 * stays the authority; these only keep the form usable while it loads.
 */
export const DEFAULT_LIMITS: ActivityLimits = {
  minQuestions: 1,
  maxQuestions: 100,
  maxChoices: 6,
};

export const MIN_QUESTIONS = DEFAULT_LIMITS.minQuestions;
export const MAX_CHOICES = DEFAULT_LIMITS.maxChoices;

/** Question types that offer a list of choices. */
export function hasChoices(type: QuestionType): boolean {
  return type === 'multiple_choice' || type === 'multi_select';
}

/** The types a teacher may pick for each kind of activity. */
export const QUESTION_TYPES_BY_KIND: Record<ActivityKind, QuestionType[]> = {
  quiz: ['multiple_choice', 'short_text', 'confidence'],
  survey: ['multiple_choice', 'multi_select', 'rating', 'short_text'],
};

export function blankChoice(): Choice {
  return { text: '', is_correct: false };
}

export function blankQuestion(
  type: QuestionType = 'multiple_choice',
  kind: ActivityKind = 'quiz'
): Question {
  return {
    prompt: '',
    question_type: type,
    is_required: true,
    // Surveys are unmarked, so asking "how sure are you?" would be noise.
    collect_confidence: kind === 'quiz' && type === 'multiple_choice',
    accepted_answers: [],
    choices: hasChoices(type) ? [blankChoice(), blankChoice()] : [],
    ...(type === 'rating' ? { rating_low_label: '', rating_high_label: '' } : {}),
  };
}

/** A single-choice question pre-filled with Yes and No. */
export function yesNoChoices(): Choice[] {
  return [
    { text: 'Yes', is_correct: false },
    { text: 'No', is_correct: false },
  ];
}

/**
 * Rewrites a question when its type changes, dropping fields that no longer
 * apply so a stale answer key cannot survive a type switch.
 */
export function changeQuestionType(question: Question, type: QuestionType): Question {
  if (type === question.question_type) return question;

  // Single choice <-> multi-select keeps the teacher's typed choices, but a
  // multi-select has no answer key.
  const keepChoices = hasChoices(type) && hasChoices(question.question_type);
  const choices = keepChoices
    ? question.choices.map((choice) => ({
        ...choice,
        is_correct: type === 'multi_select' ? false : choice.is_correct,
      }))
    : hasChoices(type)
      ? [blankChoice(), blankChoice()]
      : [];

  const next: Question = {
    ...question,
    question_type: type,
    choices,
    accepted_answers: type === 'short_text' ? question.accepted_answers : [],
    collect_confidence:
      type === 'confidence' || type === 'rating' || type === 'multi_select'
        ? false
        : question.collect_confidence,
  };
  if (type === 'rating') {
    next.rating_low_label = '';
    next.rating_high_label = '';
  } else {
    delete next.rating_low_label;
    delete next.rating_high_label;
  }
  return next;
}

/**
 * Converts existing questions when the teacher flips an activity between quiz
 * and survey, so nothing invalid is left behind (an answer key in a survey, a
 * rating in a quiz).
 */
export function convertQuestionsForKind(questions: Question[], kind: ActivityKind): Question[] {
  return questions.map((question) => {
    if (kind === 'survey') {
      const type: QuestionType =
        question.question_type === 'confidence' ? 'rating' : question.question_type;
      const converted =
        type === question.question_type ? question : changeQuestionType(question, type);
      return {
        ...converted,
        collect_confidence: false,
        accepted_answers: [],
        choices: converted.choices.map((choice) => ({ ...choice, is_correct: false })),
      };
    }
    // Survey -> quiz: survey-only types fall back to the nearest marked type.
    if (question.question_type === 'rating') return changeQuestionType(question, 'confidence');
    if (question.question_type === 'multi_select') {
      return changeQuestionType(question, 'multiple_choice');
    }
    return question;
  });
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
  kind?: ActivityKind;
}

/** Validates a draft. An empty `byQuestion` and no top-level keys means valid. */
export function validateDraft(
  draft: DraftInput,
  limits: ActivityLimits = DEFAULT_LIMITS
): DraftErrors {
  const errors: DraftErrors = { byQuestion: {} };

  if (!draft.title.trim()) errors.title = 'Give the activity a title.';
  if (!draft.classroom) errors.classroom = 'Choose the class this is for.';

  if (draft.questions.length < limits.minQuestions) {
    errors.questions = `Add at least ${limits.minQuestions} question.`;
  } else if (draft.questions.length > limits.maxQuestions) {
    errors.questions = `An activity can have at most ${limits.maxQuestions} questions.`;
  }

  draft.questions.forEach((question, index) => {
    const problem = validateQuestion(question, limits, draft.kind ?? 'quiz');
    if (problem) errors.byQuestion[index] = problem;
  });

  return errors;
}

export function validateQuestion(
  question: Question,
  limits: ActivityLimits = DEFAULT_LIMITS,
  kind: ActivityKind = 'quiz'
): string | null {
  if (!question.prompt.trim()) return 'Enter the question prompt.';
  if (question.image_id && !question.image_alt?.trim()) {
    return 'Describe the picture for students who cannot see it.';
  }

  if (hasChoices(question.question_type)) {
    const label =
      question.question_type === 'multi_select' ? 'Multi-select' : 'Multiple-choice';
    const filled = question.choices.filter((choice) => choice.text.trim().length > 0);
    if (filled.length < 2) return `${label} questions need at least two choices.`;
    if (filled.length > limits.maxChoices) return `At most ${limits.maxChoices} choices.`;

    const seen = new Set<string>();
    for (const choice of filled) {
      const key = choice.text.trim().toLowerCase();
      if (seen.has(key)) return 'Choices must be different from each other.';
      seen.add(key);
    }

    // Only a marked quiz has an answer key to get wrong.
    if (kind === 'quiz' && question.question_type === 'multiple_choice') {
      if (!filled.some((choice) => choice.is_correct))
        return 'Mark at least one choice correct.';
      // A choice marked correct but left blank would silently vanish on save.
      if (question.choices.some((c) => c.is_correct && !c.text.trim())) {
        return 'A choice marked correct has no text.';
      }
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
  const survey = draft.kind === 'survey';
  return draft.questions.map((question) => ({
    // Sending ids lets the server update rows in place, which keeps student
    // responses attached when a launched activity is edited.
    ...(question.id !== undefined ? { id: question.id } : {}),
    prompt: question.prompt.trim(),
    ...(question.image_id !== undefined
      ? {
          image_id: question.image_id,
          image_alt: question.image_id ? (question.image_alt ?? '').trim() : '',
        }
      : {}),
    question_type: question.question_type,
    ...(question.question_type === 'rating'
      ? {
          rating_low_label: (question.rating_low_label ?? '').trim(),
          rating_high_label: (question.rating_high_label ?? '').trim(),
        }
      : {}),
    is_required: question.is_required,
    collect_confidence:
      survey || question.question_type === 'confidence' ? false : question.collect_confidence,
    accepted_answers:
      !survey && question.question_type === 'short_text' ? question.accepted_answers : [],
    choices: hasChoices(question.question_type)
      ? question.choices
          .filter((choice) => choice.text.trim().length > 0)
          .map((choice) => ({
            ...(choice.id !== undefined ? { id: choice.id } : {}),
            text: choice.text.trim(),
            is_correct:
              survey || question.question_type === 'multi_select' ? false : choice.is_correct,
          }))
      : [],
  }));
}
