/** Builds same-origin Google OAuth start URLs (Django redirects to Google). */

export function googleLoginUrl(role: 'teacher' | 'student', next: string): string {
  const params = new URLSearchParams({ role, next });
  return `/api/auth/google/login/?${params.toString()}`;
}

const OAUTH_ERROR_MESSAGES: Record<string, string> = {
  domain_not_allowed: 'Your email domain is not allowed. Use your school Google account.',
  oauth_not_configured: 'Google sign-in is not configured on this server.',
  invalid_state: 'Sign-in expired. Please try again.',
  access_denied: 'Google sign-in was cancelled.',
  email_not_verified: 'Google must verify your email address before you can sign in.',
};

export function oauthErrorMessage(code: string | null): string | null {
  if (!code) return null;
  return OAUTH_ERROR_MESSAGES[code] ?? 'Google sign-in failed. Please try again.';
}
