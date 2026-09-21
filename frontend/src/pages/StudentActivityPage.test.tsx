import { afterEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes } from 'react-router-dom';
import type { PublicSession } from '@/api/types';
import { StudentActivityPage } from './StudentActivityPage';
import { renderWithProviders } from '@/test/renderWithProviders';
import { stubFetch } from '@/test/mockFetch';

const TOKEN = 'tok-123';

function publicSession(overrides: Partial<PublicSession> = {}): PublicSession {
  return {
    public_token: TOKEN,
    code: 'ABC123',
    status: 'open',
    is_open: true,
    identity_mode: 'display_name',
    activity_title: 'Networking check',
    activity_topic: 'Switches and routers',
    class_name: 'IT 4B',
    confidence_scale: { min: 1, max: 5 },
    questions: [
      {
        id: 11,
        position: 1,
        prompt: 'Which device routes between two networks?',
        question_type: 'multiple_choice',
        is_required: true,
        collect_confidence: true,
        choices: [
          { id: 101, text: 'Router', position: 1 },
          { id: 102, text: 'Switch', position: 2 },
        ],
      },
      {
        id: 12,
        position: 2,
        prompt: 'In your own words, what does a switch do?',
        question_type: 'short_text',
        is_required: false,
        collect_confidence: false,
        choices: [],
      },
    ],
    ...overrides,
  };
}

interface Options {
  session?: PublicSession;
  submit?: { status?: number; body?: unknown };
}

function renderPage({ session = publicSession(), submit }: Options = {}) {
  const bodies: unknown[] = [];

  const fetchSpy = stubFetch((url, init) => {
    if (init.body) bodies.push(JSON.parse(String(init.body)));

    if (url.includes('/join/')) {
      return {
        body: {
          participant_token: 'participant-abc',
          display_label: 'Amara J.',
          resumed: false,
          session,
        },
      };
    }
    if (url.includes('/submit/')) {
      return (
        submit ?? {
          body: {
            detail: 'Answers recorded.',
            submitted_at: '2026-03-04T10:05:00Z',
            answer_count: 2,
            activity_title: session.activity_title,
          },
        }
      );
    }
    return { body: session };
  });

  const utils = renderWithProviders(
    <Routes>
      <Route path="/s/:token" element={<StudentActivityPage />} />
    </Routes>,
    { route: `/s/${TOKEN}` }
  );

  return { ...utils, fetchSpy, bodies };
}

async function join(user: ReturnType<typeof userEvent.setup>, name = 'Amara J.') {
  await user.type(await screen.findByLabelText(/your name/i), name);
  await user.click(screen.getByRole('button', { name: /start/i }));
}

describe('StudentActivityPage', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('asks for a name, then shows the questions', async () => {
    const user = userEvent.setup();
    renderPage();

    expect(
      await screen.findByRole('heading', { name: 'Networking check' })
    ).toBeInTheDocument();
    await join(user);

    expect(
      await screen.findByText('Which device routes between two networks?')
    ).toBeInTheDocument();
    expect(screen.getByText('In your own words, what does a switch do?')).toBeInTheDocument();
  });

  it('labels the identifier field for the roster join mode', async () => {
    renderPage({ session: publicSession({ identity_mode: 'roster_identifier' }) });
    expect(await screen.findByLabelText(/roster identifier/i)).toBeInTheDocument();
  });

  it('blocks submission until required questions are answered', async () => {
    const user = userEvent.setup();
    const { bodies } = renderPage();
    await join(user);

    await user.click(await screen.findByRole('button', { name: /submit answers/i }));

    expect(await screen.findByText(/please answer question 1/i)).toBeInTheDocument();
    // Nothing was sent, so the student keeps their single submission.
    expect(bodies.some((body) => body && 'answers' in (body as object))).toBe(false);
  });

  // The MCQ collects confidence, so answering the question alone is not
  // enough — otherwise the confidence signal would silently be half-empty.
  it('asks for confidence before accepting the answer', async () => {
    const user = userEvent.setup();
    renderPage();
    await join(user);

    await user.click(await screen.findByRole('radio', { name: /router/i }));
    await user.click(screen.getByRole('button', { name: /submit answers/i }));

    expect(await screen.findByText('Pick a rating from 1 to 5.')).toBeInTheDocument();
  });

  it('sends only answered questions and confirms once', async () => {
    const user = userEvent.setup();
    const { bodies } = renderPage();
    await join(user);

    await user.click(await screen.findByRole('radio', { name: /router/i }));
    await user.click(screen.getByRole('radio', { name: /very sure/i }));
    await user.click(screen.getByRole('button', { name: /submit answers/i }));

    expect(await screen.findByRole('heading', { name: /answers sent/i })).toBeInTheDocument();
    // The form is gone, so there is nothing left to submit twice.
    expect(screen.queryByRole('button', { name: /submit answers/i })).not.toBeInTheDocument();

    const submission = bodies.find((body) => body && 'answers' in (body as object)) as {
      participant_token: string;
      answers: { question: number; selected_choice?: number; confidence_value?: number }[];
    };
    expect(submission.participant_token).toBe('participant-abc');
    expect(submission.answers).toEqual([
      { question: 11, selected_choice: 101, confidence_value: 5 },
    ]);
  });

  it('surfaces a rejected submission without losing the answers', async () => {
    const user = userEvent.setup();
    renderPage({
      submit: {
        status: 409,
        body: {
          detail: 'You have already submitted your answers.',
          code: 'already_submitted',
          errors: {},
        },
      },
    });
    await join(user);

    await user.click(await screen.findByRole('radio', { name: /router/i }));
    await user.click(screen.getByRole('radio', { name: /very sure/i }));
    await user.click(screen.getByRole('button', { name: /submit answers/i }));

    expect(
      await screen.findByText('You have already submitted your answers.')
    ).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: /router/i })).toBeChecked();
  });

  it('does not offer a form once the teacher has closed the session', async () => {
    renderPage({ session: publicSession({ is_open: false, status: 'closed' }) });

    expect(await screen.findByText(/this activity is closed/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /start/i })).not.toBeInTheDocument();
  });

  it('tells the student when the link is not valid', async () => {
    stubFetch(() => ({
      status: 404,
      body: { detail: 'Session not found.', code: 'not_found', errors: {} },
    }));

    renderWithProviders(
      <Routes>
        <Route path="/s/:token" element={<StudentActivityPage />} />
      </Routes>,
      { route: '/s/nope' }
    );

    expect(await screen.findByText(/activity not found/i)).toBeInTheDocument();
  });

  it('shows progress as questions are answered', async () => {
    const user = userEvent.setup();
    renderPage();
    await join(user);

    expect(await screen.findByText('0 of 2 answered')).toBeInTheDocument();
    await user.click(screen.getByRole('radio', { name: /router/i }));
    await waitFor(() => expect(screen.getByText('1 of 2 answered')).toBeInTheDocument());
  });
});
