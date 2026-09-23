import { createApi } from '@reduxjs/toolkit/query/react';
import { baseQuery } from './baseQuery';
import type {
  Activity,
  ActivityImportResult,
  ActivityListItem,
  ActivityWritePayload,
  ClassJoinResult,
  ClientConfig,
  Classroom,
  PublicClassInfo,
  StudentAccount,
  DashboardResponse,
  Enrollment,
  HealthResponse,
  IdentityMode,
  LiveSession,
  Paginated,
  PlanImpact,
  PublicJoinResult,
  PublicSession,
  PublicSubmitResult,
  PublicAnswer,
  RosterImportResult,
  SessionResults,
  Student,
  Teacher,
  TeacherOverview,
  TeacherReflection,
  TopicTimelineGroup,
} from './types';

export const caricueApi = createApi({
  reducerPath: 'caricueApi',
  baseQuery,
  tagTypes: [
    'Teacher',
    'Classroom',
    'Roster',
    'Student',
    'Activity',
    'Session',
    'Dashboard',
    'Reflection',
    'Overview',
  ],
  endpoints: (build) => ({
    // -- meta ------------------------------------------------------------ //
    health: build.query<HealthResponse, void>({
      query: () => 'health/',
    }),
    clientConfig: build.query<ClientConfig, void>({
      query: () => 'config/',
    }),

    // -- authentication -------------------------------------------------- //
    csrf: build.query<{ csrf_token: string }, void>({
      query: () => 'auth/csrf/',
    }),
    currentTeacher: build.query<Teacher, void>({
      query: () => 'auth/me/',
      providesTags: ['Teacher'],
    }),
    register: build.mutation<
      Teacher,
      { email: string; full_name: string; school_name?: string; password: string }
    >({
      query: (body) => ({ url: 'auth/register/', method: 'POST', body }),
      invalidatesTags: ['Teacher', 'Overview'],
    }),
    login: build.mutation<Teacher, { email: string; password: string }>({
      query: (body) => ({ url: 'auth/login/', method: 'POST', body }),
      invalidatesTags: ['Teacher', 'Overview', 'Classroom', 'Activity', 'Session'],
    }),
    logout: build.mutation<void, void>({
      query: () => ({ url: 'auth/logout/', method: 'POST' }),
      // Drops every cached teacher-scoped response on sign-out.
      invalidatesTags: [
        'Teacher',
        'Overview',
        'Classroom',
        'Roster',
        'Student',
        'Activity',
        'Session',
        'Dashboard',
        'Reflection',
      ],
    }),
    updateProfile: build.mutation<Teacher, Partial<Pick<Teacher, 'full_name' | 'school_name'>>>(
      {
        query: (body) => ({ url: 'auth/me/', method: 'PATCH', body }),
        invalidatesTags: ['Teacher'],
      }
    ),
    studentMe: build.query<StudentAccount, void>({
      query: () => 'auth/student/me/',
    }),
    studentLogout: build.mutation<void, void>({
      query: () => ({ url: 'auth/student/logout/', method: 'POST' }),
    }),

    // -- dashboard ------------------------------------------------------- //
    overview: build.query<TeacherOverview, void>({
      query: () => 'overview/',
      providesTags: ['Overview'],
    }),

    // -- classes --------------------------------------------------------- //
    classrooms: build.query<Paginated<Classroom>, void>({
      query: () => 'classrooms/',
      providesTags: ['Classroom'],
    }),
    classroom: build.query<Classroom, number>({
      query: (id) => `classrooms/${id}/`,
      providesTags: (_r, _e, id) => [{ type: 'Classroom', id }],
    }),
    createClassroom: build.mutation<Classroom, Partial<Classroom>>({
      query: (body) => ({ url: 'classrooms/', method: 'POST', body }),
      invalidatesTags: ['Classroom', 'Overview'],
    }),
    updateClassroom: build.mutation<Classroom, { id: number; body: Partial<Classroom> }>({
      query: ({ id, body }) => ({ url: `classrooms/${id}/`, method: 'PATCH', body }),
      invalidatesTags: (_r, _e, { id }) => [{ type: 'Classroom', id }, 'Classroom', 'Overview'],
    }),
    deleteClassroom: build.mutation<void, number>({
      query: (id) => ({ url: `classrooms/${id}/`, method: 'DELETE' }),
      invalidatesTags: ['Classroom', 'Overview', 'Activity'],
    }),
    topicTimeline: build.query<TopicTimelineGroup[], number>({
      query: (classroomId) => `classrooms/${classroomId}/topic-timeline/`,
      providesTags: (_r, _e, id) => [{ type: 'Classroom', id }],
    }),

    // -- roster ---------------------------------------------------------- //
    roster: build.query<Enrollment[], number>({
      query: (classroomId) => `classrooms/${classroomId}/roster/`,
      providesTags: (_r, _e, id) => [{ type: 'Roster', id }],
    }),
    addStudentToClass: build.mutation<
      Student,
      {
        classroomId: number;
        body: { display_name: string; school_identifier?: string; email?: string };
      }
    >({
      query: ({ classroomId, body }) => ({
        url: `classrooms/${classroomId}/students/`,
        method: 'POST',
        body,
      }),
      invalidatesTags: (_r, _e, { classroomId }) => [
        { type: 'Roster', id: classroomId },
        { type: 'Classroom', id: classroomId },
        'Classroom',
        'Overview',
      ],
    }),
    importRoster: build.mutation<RosterImportResult, { classroomId: number; file: File }>({
      query: ({ classroomId, file }) => {
        const form = new FormData();
        form.append('file', file);
        return {
          url: `classrooms/${classroomId}/import-roster/`,
          method: 'POST',
          body: form,
          // Let the browser set the multipart boundary.
          formData: true,
        };
      },
      invalidatesTags: (_r, _e, { classroomId }) => [
        { type: 'Roster', id: classroomId },
        { type: 'Classroom', id: classroomId },
        'Classroom',
        'Overview',
      ],
    }),
    removeEnrollment: build.mutation<void, { id: number; classroomId: number }>({
      query: ({ id }) => ({ url: `enrollments/${id}/`, method: 'DELETE' }),
      invalidatesTags: (_r, _e, { classroomId }) => [
        { type: 'Roster', id: classroomId },
        { type: 'Classroom', id: classroomId },
        'Classroom',
        'Overview',
      ],
    }),

    // -- activities ------------------------------------------------------ //
    activities: build.query<Paginated<ActivityListItem>, { classroom?: number } | void>({
      query: (args) => {
        const classroom = args && 'classroom' in args ? args.classroom : undefined;
        return classroom ? `activities/?classroom=${classroom}` : 'activities/';
      },
      providesTags: ['Activity'],
    }),
    activity: build.query<Activity, number>({
      query: (id) => `activities/${id}/`,
      providesTags: (_r, _e, id) => [{ type: 'Activity', id }],
    }),
    createActivity: build.mutation<Activity, ActivityWritePayload>({
      query: (body) => ({ url: 'activities/', method: 'POST', body }),
      invalidatesTags: ['Activity', 'Overview'],
    }),
    updateActivity: build.mutation<Activity, { id: number; body: ActivityWritePayload }>({
      query: ({ id, body }) => ({ url: `activities/${id}/`, method: 'PUT', body }),
      invalidatesTags: (_r, _e, { id }) => [{ type: 'Activity', id }, 'Activity', 'Overview'],
    }),
    deleteActivity: build.mutation<void, number>({
      query: (id) => ({ url: `activities/${id}/`, method: 'DELETE' }),
      invalidatesTags: ['Activity', 'Overview'],
    }),
    importActivity: build.mutation<ActivityImportResult, { classroom: number; file: File }>({
      query: ({ classroom, file }) => {
        const form = new FormData();
        form.append('classroom', String(classroom));
        form.append('file', file);
        return {
          url: 'activities/import/',
          method: 'POST',
          body: form,
          formData: true,
        };
      },
      invalidatesTags: ['Activity', 'Overview'],
    }),

    // -- sessions -------------------------------------------------------- //
    launchSession: build.mutation<
      LiveSession,
      { activityId: number; identity_mode: IdentityMode }
    >({
      query: ({ activityId, identity_mode }) => ({
        url: `activities/${activityId}/launch/`,
        method: 'POST',
        body: { identity_mode },
      }),
      invalidatesTags: ['Session', 'Activity', 'Overview'],
    }),
    sessions: build.query<
      Paginated<LiveSession>,
      { status?: 'open' | 'closed'; classroom?: number } | void
    >({
      query: (args) => {
        const params = new URLSearchParams();
        if (args && 'status' in args && args.status) params.set('status', args.status);
        if (args && 'classroom' in args && args.classroom) {
          params.set('classroom', String(args.classroom));
        }
        const qs = params.toString();
        return qs ? `sessions/?${qs}` : 'sessions/';
      },
      providesTags: ['Session'],
    }),
    session: build.query<LiveSession, number>({
      query: (id) => `sessions/${id}/`,
      providesTags: (_r, _e, id) => [{ type: 'Session', id }],
    }),
    closeSession: build.mutation<LiveSession, number>({
      query: (id) => ({ url: `sessions/${id}/close/`, method: 'POST' }),
      invalidatesTags: (_r, _e, id) => [
        { type: 'Session', id },
        'Session',
        'Dashboard',
        'Overview',
      ],
    }),
    /** Polled every few seconds while a session is open. */
    sessionDashboard: build.query<DashboardResponse, number>({
      query: (id) => `sessions/${id}/dashboard/`,
      providesTags: (_r, _e, id) => [{ type: 'Dashboard', id }],
    }),
    sessionResults: build.query<SessionResults, number>({
      query: (id) => `sessions/${id}/results/`,
      providesTags: (_r, _e, id) => [
        { type: 'Dashboard', id },
        { type: 'Reflection', id },
      ],
    }),
    createFollowUpActivity: build.mutation<
      { activity_id: number },
      { sessionId: number; question_ids?: number[]; include_confidence?: boolean }
    >({
      query: ({ sessionId, question_ids, include_confidence }) => ({
        url: `sessions/${sessionId}/follow-up-activity/`,
        method: 'POST',
        body: { question_ids, include_confidence },
      }),
      invalidatesTags: ['Activity', 'Overview'],
    }),

    // -- reflections ----------------------------------------------------- //
    createReflection: build.mutation<
      TeacherReflection,
      {
        live_session: number;
        primary_gap: string;
        plan_impact: PlanImpact;
        planned_action: string;
        notes?: string;
      }
    >({
      query: (body) => ({ url: 'reflections/', method: 'POST', body }),
      invalidatesTags: (_r, _e, { live_session }) => [
        { type: 'Reflection', id: live_session },
        { type: 'Dashboard', id: live_session },
        { type: 'Session', id: live_session },
        'Session',
        'Overview',
      ],
    }),
    updateReflection: build.mutation<
      TeacherReflection,
      { id: number; live_session: number; body: Partial<TeacherReflection> }
    >({
      query: ({ id, body }) => ({ url: `reflections/${id}/`, method: 'PATCH', body }),
      invalidatesTags: (_r, _e, { live_session }) => [
        { type: 'Reflection', id: live_session },
        { type: 'Dashboard', id: live_session },
        'Overview',
      ],
    }),

    // -- public student endpoints ---------------------------------------- //
    lookupCode: build.query<{ public_token: string; join_url: string }, string>({
      query: (code) => `public/sessions/lookup/?code=${encodeURIComponent(code)}`,
    }),
    publicSession: build.query<PublicSession, string>({
      query: (token) => `public/sessions/${token}/`,
    }),
    joinSession: build.mutation<PublicJoinResult, { token: string; identifier?: string }>({
      query: ({ token, identifier }) => ({
        url: `public/sessions/${token}/join/`,
        method: 'POST',
        body: identifier ? { identifier } : {},
      }),
    }),
    publicClass: build.query<PublicClassInfo, string>({
      query: (inviteToken) => `public/classes/${inviteToken}/`,
    }),
    joinClass: build.mutation<ClassJoinResult, string>({
      query: (inviteToken) => ({
        url: `public/classes/${inviteToken}/join/`,
        method: 'POST',
        body: {},
      }),
    }),
    submitAnswers: build.mutation<
      PublicSubmitResult,
      { token: string; participant_token: string; answers: PublicAnswer[] }
    >({
      query: ({ token, participant_token, answers }) => ({
        url: `public/sessions/${token}/submit/`,
        method: 'POST',
        body: { participant_token, answers },
      }),
    }),
  }),
});

export const {
  useHealthQuery,
  useClientConfigQuery,
  useCsrfQuery,
  useCurrentTeacherQuery,
  useRegisterMutation,
  useLoginMutation,
  useLogoutMutation,
  useUpdateProfileMutation,
  useStudentMeQuery,
  useStudentLogoutMutation,
  useOverviewQuery,
  useClassroomsQuery,
  useClassroomQuery,
  useCreateClassroomMutation,
  useUpdateClassroomMutation,
  useDeleteClassroomMutation,
  useTopicTimelineQuery,
  useRosterQuery,
  useAddStudentToClassMutation,
  useImportRosterMutation,
  useRemoveEnrollmentMutation,
  useActivitiesQuery,
  useActivityQuery,
  useCreateActivityMutation,
  useUpdateActivityMutation,
  useDeleteActivityMutation,
  useImportActivityMutation,
  useLaunchSessionMutation,
  useSessionsQuery,
  useSessionQuery,
  useCloseSessionMutation,
  useSessionDashboardQuery,
  useSessionResultsQuery,
  useCreateFollowUpActivityMutation,
  useCreateReflectionMutation,
  useUpdateReflectionMutation,
  useLazyLookupCodeQuery,
  usePublicSessionQuery,
  useJoinSessionMutation,
  usePublicClassQuery,
  useJoinClassMutation,
  useSubmitAnswersMutation,
} = caricueApi;
