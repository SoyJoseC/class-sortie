import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type * as RouterDom from 'react-router-dom';
import { LoginPage } from './LoginPage';
import { renderWithProviders } from '@/test/renderWithProviders';
import { stubFetch } from '@/test/mockFetch';

const navigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof RouterDom>('react-router-dom');
  return { ...actual, useNavigate: () => navigate };
});

function fill(email: string, password: string) {
  fireEvent.change(screen.getByLabelText(/email address/i), { target: { value: email } });
  fireEvent.change(screen.getByLabelText(/password/i), { target: { value: password } });
}

describe('LoginPage', () => {
  beforeEach(() => {
    navigate.mockClear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('validates locally before calling the API', async () => {
    const fetchSpy = stubFetch(() => ({ body: {} }));
    const user = userEvent.setup();
    renderWithProviders(<LoginPage />);

    await user.click(screen.getByRole('button', { name: /sign in/i }));

    expect(await screen.findByText('Enter your email address.')).toBeInTheDocument();
    expect(screen.getByText('Enter your password.')).toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('signs in and lands on the dashboard', async () => {
    const fetchSpy = stubFetch(() => ({
      body: { id: 1, email: 'teacher@school.edu', full_name: 'Ms Grant' },
    }));
    const user = userEvent.setup();
    renderWithProviders(<LoginPage />);

    fill('teacher@school.edu', 'correct-horse');
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => expect(navigate).toHaveBeenCalledWith('/app', { replace: true }));

    const login = fetchSpy.mock.calls.find(([input]) => String(input).includes('auth/login'));
    expect(login).toBeDefined();
  });

  // Bad credentials come back as a single detail message, not a field error,
  // so the form must show it somewhere rather than swallowing it.
  it('shows the server message when the credentials are rejected', async () => {
    stubFetch((url) =>
      url.includes('auth/login')
        ? {
            status: 400,
            body: {
              detail: 'Email or password is incorrect.',
              code: 'invalid_credentials',
              errors: {},
            },
          }
        : { body: {} }
    );
    const user = userEvent.setup();
    renderWithProviders(<LoginPage />);

    fill('teacher@school.edu', 'wrong');
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    expect(await screen.findByText('Email or password is incorrect.')).toBeInTheDocument();
    expect(navigate).not.toHaveBeenCalled();
  });

  it('places field errors from the server next to the input', async () => {
    stubFetch((url) =>
      url.includes('auth/login')
        ? {
            status: 400,
            body: {
              detail: 'Invalid input.',
              code: 'invalid',
              errors: { email: ['No account uses that address.'] },
            },
          }
        : { body: {} }
    );
    const user = userEvent.setup();
    renderWithProviders(<LoginPage />);

    fill('nobody@school.edu', 'whatever');
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    expect(await screen.findByText('No account uses that address.')).toBeInTheDocument();
  });

  it('points students at the join flow instead of an account', () => {
    stubFetch(() => ({ body: {} }));
    renderWithProviders(<LoginPage />);

    expect(screen.getByRole('link', { name: /join with a session code/i })).toHaveAttribute(
      'href',
      '/join'
    );
  });
});
