import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type * as RouterDom from 'react-router-dom';
import { StudentJoinPage } from './StudentJoinPage';
import { renderWithProviders } from '@/test/renderWithProviders';
import { requestedUrls, stubFetch } from '@/test/mockFetch';

const navigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof RouterDom>('react-router-dom');
  return { ...actual, useNavigate: () => navigate };
});

describe('StudentJoinPage', () => {
  beforeEach(() => {
    navigate.mockClear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('keeps Join disabled until the code is six characters', async () => {
    stubFetch(() => ({ body: {} }));
    const user = userEvent.setup();
    renderWithProviders(<StudentJoinPage />);

    const join = screen.getByRole('button', { name: /join/i });
    expect(join).toBeDisabled();

    await user.type(screen.getByLabelText(/session code/i), 'ABC12');
    expect(join).toBeDisabled();

    await user.type(screen.getByLabelText(/session code/i), '3');
    expect(join).toBeEnabled();
  });

  // Students read the code off a whiteboard, so lowercase and stray spaces
  // are the norm rather than an error worth showing them.
  it('normalises what the student types before looking it up', async () => {
    const fetchSpy = stubFetch(() => ({
      body: { public_token: 'tok-123', join_url: 'https://caricue.test/s/tok-123' },
    }));

    const user = userEvent.setup();
    renderWithProviders(<StudentJoinPage />);

    await user.type(screen.getByLabelText(/session code/i), 'abc 123');
    await user.click(screen.getByRole('button', { name: /join/i }));

    await waitFor(() => expect(navigate).toHaveBeenCalledWith('/s/tok-123'));
    expect(requestedUrls(fetchSpy).join(' ')).toContain('code=ABC123');
  });

  it('shows the server message when no open session matches', async () => {
    stubFetch(() => ({
      status: 404,
      body: { detail: 'No open session with that code.', code: 'not_found', errors: {} },
    }));

    const user = userEvent.setup();
    renderWithProviders(<StudentJoinPage />);

    await user.type(screen.getByLabelText(/session code/i), 'ZZZ999');
    await user.click(screen.getByRole('button', { name: /join/i }));

    expect(await screen.findByText('No open session with that code.')).toBeInTheDocument();
    expect(navigate).not.toHaveBeenCalled();
  });

  it('resolves a code passed in the query string, as a QR scan does', async () => {
    stubFetch(() => ({ body: { public_token: 'tok-999', join_url: 'x' } }));
    renderWithProviders(<StudentJoinPage />, { route: '/join?code=xyz789' });

    await waitFor(() => expect(navigate).toHaveBeenCalledWith('/s/tok-999'));
  });
});
