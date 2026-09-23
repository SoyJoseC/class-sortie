import { Navigate, Route, Routes } from 'react-router-dom';
import { TeacherLayout } from '@/components/TeacherLayout';
import { RequireTeacher } from '@/components/RequireTeacher';
import { LoginPage } from '@/pages/LoginPage';
import { RegisterPage } from '@/pages/RegisterPage';
import { DashboardPage } from '@/pages/DashboardPage';
import { ClassListPage } from '@/pages/ClassListPage';
import { ClassFormPage } from '@/pages/ClassFormPage';
import { ClassDetailPage } from '@/pages/ClassDetailPage';
import { ActivityListPage } from '@/pages/ActivityListPage';
import { ActivityBuilderPage } from '@/pages/ActivityBuilderPage';
import { SessionListPage } from '@/pages/SessionListPage';
import { SessionLaunchPage } from '@/pages/SessionLaunchPage';
import { SessionLivePage } from '@/pages/SessionLivePage';
import { SessionReflectionPage } from '@/pages/SessionReflectionPage';
import { ProfilePage } from '@/pages/ProfilePage';
import { ClassJoinPage } from '@/pages/ClassJoinPage';
import { StudentJoinPage } from '@/pages/StudentJoinPage';
import { StudentActivityPage } from '@/pages/StudentActivityPage';
import { NotFoundPage } from '@/pages/NotFoundPage';

/**
 * Two distinct route trees.
 *
 * `/app/*` is the authenticated teacher application. `/join` and `/s/:token`
 * are public, account-free student pages and deliberately share no layout,
 * navigation, or teacher-scoped data fetching with the teacher tree.
 */
export function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/app" replace />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

      <Route
        path="/app"
        element={
          <RequireTeacher>
            <TeacherLayout />
          </RequireTeacher>
        }
      >
        <Route index element={<DashboardPage />} />
        <Route path="classes" element={<ClassListPage />} />
        <Route path="classes/new" element={<ClassFormPage />} />
        <Route path="classes/:id" element={<ClassDetailPage />} />
        <Route path="classes/:id/edit" element={<ClassFormPage />} />
        <Route path="activities" element={<ActivityListPage />} />
        <Route path="activities/new" element={<ActivityBuilderPage />} />
        <Route path="activities/:id" element={<ActivityBuilderPage />} />
        <Route path="sessions" element={<SessionListPage />} />
        <Route path="sessions/:id" element={<SessionLivePage />} />
        <Route path="sessions/:id/launch" element={<SessionLaunchPage />} />
        <Route path="sessions/:id/reflection" element={<SessionReflectionPage />} />
        <Route path="profile" element={<ProfilePage />} />
      </Route>

      <Route path="/join" element={<StudentJoinPage />} />
      <Route path="/join/class/:inviteToken" element={<ClassJoinPage />} />
      <Route path="/s/:token" element={<StudentActivityPage />} />

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
