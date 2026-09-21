import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes } from 'react-router-dom';
import { ActivityBuilderPage } from './ActivityBuilderPage';
import { renderWithProviders } from '@/test/renderWithProviders';
import { stubFetch } from '@/test/mockFetch';

const CLASSROOM = {
  id: 7,
  name: 'IT 4B',
  subject: 'Information Technology',
  level: 'Form 4',
  academic_period: '2026 Term 2',
  is_active: true,
  roster_size: 24,
  activity_count: 2,
  created_at: '2026-02-01T09:00:00Z',
  updated_at: '2026-02-01T09:00:00Z',
};

function renderBuilder({ launchStatus = 200 }: { launchStatus?: number } = {}) {
  const bodies: { url: string; body: Record<string, unknown> }[] = [];

  const fetchSpy = stubFetch((url, init) => {
    if (init.body) {
      bodies.push({ url, body: JSON.parse(String(init.body)) });
    }

    if (url.includes('/classrooms/')) {
      return { body: { count: 1, next: null, previous: null, results: [CLASSROOM] } };
    }
    if (url.includes('/launch/')) {
      return launchStatus === 200
        ? { body: { id: 55, code: 'ABC123', status: 'open' } }
        : {
            status: launchStatus,
            body: {
              detail: 'This activity has no questions yet.',
              code: 'not_launchable',
              errors: {},
            },
          };
    }
    if (url.includes('/activities/')) {
      return { body: { id: 42, title: 'Networking check', questions: [] } };
    }
    return { body: { id: 42, title: 'Networking check', questions: [] } };
  });

  const utils = renderWithProviders(
    <Routes>
      <Route path="/app/activities/new" element={<ActivityBuilderPage />} />
    </Routes>,
    { route: '/app/activities/new' }
  );

  return { ...utils, fetchSpy, bodies };
}

/**
 * Controlled inputs re-render the whole builder (including the live preview)
 * on every keystroke, so these tests set values with a single change event
 * and reserve `userEvent` for the clicks whose handlers are under test.
 */
function setValue(element: HTMLElement, value: string) {
  fireEvent.change(element, { target: { value } });
}

async function fillValidQuestion(user: ReturnType<typeof userEvent.setup>) {
  setValue(screen.getByLabelText('Prompt'), 'Which device routes between networks?');
  setValue(screen.getByLabelText(/choice 1 text/i), 'Router');
  setValue(screen.getByLabelText(/choice 2 text/i), 'Switch');
  await user.click(screen.getByLabelText(/choice 1 of question 1 is correct/i));
}

describe('ActivityBuilderPage', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('starts with one multiple-choice question and two empty choices', async () => {
    renderBuilder();

    expect(
      await screen.findByRole('heading', { name: /create an activity/i })
    ).toBeInTheDocument();
    expect(screen.getByText('Questions (1/5)')).toBeInTheDocument();
    expect(screen.getByLabelText(/choice 1 text/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/choice 2 text/i)).toBeInTheDocument();
  });

  it('preselects the only class the teacher has', async () => {
    renderBuilder();
    await waitFor(() =>
      expect(screen.getByLabelText(/^class/i)).toHaveValue(String(CLASSROOM.id))
    );
  });

  // The server would reject these too; catching them here saves the teacher a
  // round trip mid-lesson.
  it('reports missing title and answer key without calling the API', async () => {
    const user = userEvent.setup();
    const { bodies } = renderBuilder();

    await user.click(await screen.findByRole('button', { name: /save draft/i }));

    expect(await screen.findByText('Give the activity a title.')).toBeInTheDocument();
    expect(screen.getByText('Enter the question prompt.')).toBeInTheDocument();
    expect(bodies).toHaveLength(0);
  });

  it('requires a correct choice to be marked', async () => {
    const user = userEvent.setup();
    renderBuilder();

    setValue(await screen.findByLabelText(/^title/i), 'Networking check');
    setValue(screen.getByLabelText('Prompt'), 'Which device routes between networks?');
    setValue(screen.getByLabelText(/choice 1 text/i), 'Router');
    setValue(screen.getByLabelText(/choice 2 text/i), 'Switch');
    await user.click(screen.getByRole('button', { name: /save draft/i }));

    expect(await screen.findByText('Mark at least one choice correct.')).toBeInTheDocument();
  });

  it('sends a trimmed payload without positions when the draft is valid', async () => {
    const user = userEvent.setup();
    const { bodies } = renderBuilder();

    setValue(await screen.findByLabelText(/^title/i), '  Networking check  ');
    setValue(screen.getByLabelText(/topic or learning objective/i), 'Switches and routers');
    await fillValidQuestion(user);
    await user.click(screen.getByRole('button', { name: /save draft/i }));

    await waitFor(() => expect(bodies).toHaveLength(1));
    expect(bodies[0].body).toMatchObject({
      classroom: CLASSROOM.id,
      title: 'Networking check',
      topic: 'Switches and routers',
      status: 'draft',
    });

    const questions = bodies[0].body.questions as Record<string, unknown>[];
    expect(questions).toHaveLength(1);
    expect(questions[0]).not.toHaveProperty('position');
    expect(questions[0].choices).toEqual([
      { text: 'Router', is_correct: true },
      { text: 'Switch', is_correct: false },
    ]);
  });

  it('caps an activity at five questions', async () => {
    const user = userEvent.setup();
    renderBuilder();

    const add = await screen.findByRole('button', { name: /add question/i });
    for (let i = 0; i < 4; i += 1) await user.click(add);

    expect(screen.getByText('Questions (5/5)')).toBeInTheDocument();
    expect(add).toBeDisabled();
  });

  it('swaps the answer key when the question type changes', async () => {
    const user = userEvent.setup();
    renderBuilder();

    await user.selectOptions(await screen.findByLabelText(/question type/i), 'short_text');

    expect(screen.queryByLabelText(/choice 1 text/i)).not.toBeInTheDocument();
    expect(screen.getByLabelText(/accepted answers/i)).toBeInTheDocument();
  });

  it('reorders questions', async () => {
    const user = userEvent.setup();
    renderBuilder();

    await user.click(await screen.findByRole('button', { name: /add question/i }));
    setValue(screen.getAllByLabelText('Prompt')[0], 'First');
    setValue(screen.getAllByLabelText('Prompt')[1], 'Second');

    await user.click(screen.getByRole('button', { name: /move question 2 up/i }));

    expect(screen.getAllByLabelText('Prompt')[0]).toHaveValue('Second');
    expect(screen.getAllByLabelText('Prompt')[1]).toHaveValue('First');
  });

  it('saves before launching, so the session matches what is on screen', async () => {
    const user = userEvent.setup();
    const { bodies } = renderBuilder();

    setValue(await screen.findByLabelText(/^title/i), 'Networking check');
    await fillValidQuestion(user);
    await user.click(screen.getByRole('button', { name: /launch now/i }));

    await waitFor(() => expect(bodies).toHaveLength(2));
    expect(bodies[0].url).toContain('/activities/');
    expect(bodies[1].url).toContain('/launch/');
    expect(bodies[1].body).toEqual({ identity_mode: 'display_name' });
  });

  it('shows the server error when a launch is refused', async () => {
    const user = userEvent.setup();
    renderBuilder({ launchStatus: 400 });

    setValue(await screen.findByLabelText(/^title/i), 'Networking check');
    await fillValidQuestion(user);
    await user.click(screen.getByRole('button', { name: /launch now/i }));

    expect(await screen.findByText('This activity has no questions yet.')).toBeInTheDocument();
  });

  it('mirrors the draft in the student preview', async () => {
    renderBuilder();

    setValue(await screen.findByLabelText(/^title/i), 'Networking check');
    setValue(screen.getByLabelText('Prompt'), 'Which device routes between networks?');
    setValue(screen.getByLabelText(/choice 1 text/i), 'Router');

    const preview = screen.getByLabelText('Student preview');
    expect(within(preview).getByText('Networking check')).toBeInTheDocument();
    expect(
      within(preview).getByText(/1\. Which device routes between networks\?/)
    ).toBeInTheDocument();
    expect(within(preview).getByText('Router')).toBeInTheDocument();
  });
});
