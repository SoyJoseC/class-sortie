import { Navigate, useLocation } from 'react-router-dom';
import type { ReactNode } from 'react';
import { useCurrentTeacherQuery } from '@/api/caricueApi';
import { LoadingState } from './StateViews';

/**
 * Route guard.
 *
 * The check is a real request to `/api/auth/me/`: whether a teacher is signed
 * in is decided by the server-side session, never by anything in local
 * storage. This is a UX guard only — every endpoint enforces ownership on its
 * own.
 */
export function RequireTeacher({ children }: { children: ReactNode }) {
  const location = useLocation();
  const { data, isLoading, isError, error } = useCurrentTeacherQuery();

  if (isLoading) return <LoadingState label="Checking your session…" />;

  const status = (error as { status?: number } | undefined)?.status;
  if (isError && (status === 401 || status === 403)) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  if (!data) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  return <>{children}</>;
}
