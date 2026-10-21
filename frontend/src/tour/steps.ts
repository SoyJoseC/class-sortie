import type { TourSegment } from './tourSlice';

export type { TourSegment };

export interface TourStep {
  element: string;
  title: string;
  description: string;
}

export const TOUR_STEPS: Record<TourSegment, TourStep[]> = {
  class: [
    {
      element: '[data-tour="class-name"]',
      title: 'Name the class',
      description:
        'This is how the class appears on your dashboard and on the student join screen.',
    },
    {
      element: '[data-tour="class-subject"]',
      title: 'Add a subject',
      description: 'Optional, but it helps you find the class later.',
    },
    {
      element: '[data-tour="class-save"]',
      title: 'Save, then add students',
      description:
        'After you create the class you can add students by hand or import a roster.',
    },
  ],
  activity: [
    {
      element: '[data-tour="activity-title"]',
      title: 'Give the check a title',
      description: 'Students see this at the top of their phone.',
    },
    {
      element: '[data-tour="activity-classroom"]',
      title: 'Pick the class',
      description: 'The session is tied to one class so results stay together.',
    },
    {
      element: '[data-tour="activity-question"]',
      title: 'Write a question',
      description: 'A quiz is marked. A survey is unmarked. Add as many questions as you need.',
    },
    {
      element: '[data-tour="activity-preview"]',
      title: 'Student preview',
      description: 'This is what they see. Correct answers never leave your side.',
    },
    {
      element: '[data-tour="activity-launch"]',
      title: 'Launch when you are ready',
      description: 'Saves the draft and opens a live session with a code and QR.',
    },
  ],
  reflection: [
    {
      element: '[data-tour="session-code"]',
      title: 'Show the code',
      description: 'Students type this short code, or scan the QR, to join.',
    },
    {
      element: '[data-tour="session-live"]',
      title: 'Watch answers come in',
      description: 'Figures here are measured facts. Suggestions are labelled separately.',
    },
    {
      element: '[data-tour="session-next-step"]',
      title: 'Record what you will do next',
      description: 'The last step of the loop: name the gap and say what changes tomorrow.',
    },
  ],
};

export const SEGMENT_LABELS: Record<TourSegment, string> = {
  class: 'Create a class',
  activity: 'Create an activity',
  reflection: 'Run a session and record the next step',
};
