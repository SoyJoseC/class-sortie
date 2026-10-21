/** Shapes returned by the CariCue API. Mirrors the DRF serializers. */

export type QuestionType =
  'multiple_choice' | 'multi_select' | 'rating' | 'short_text' | 'confidence';
/** A quiz is marked; a survey is unmarked and collects opinions. */
export type ActivityKind = 'quiz' | 'survey';
export type ActivityStatus = 'draft' | 'published';
export type SessionStatus = 'open' | 'closed';
export type IdentityMode =
  'display_name' | 'roster_identifier' | 'google_account' | 'anonymous';
export type PlanImpact = 'confirmed' | 'changed' | 'unclear';

/** Uniform error envelope produced by `core.exceptions.safe_exception_handler`. */
export interface ApiError {
  detail: string;
  code: string;
  errors: Record<string, string[] | Record<string, string[]>>;
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export type TourSegment = 'class' | 'activity' | 'reflection';

export interface TeacherOnboarding {
  dismissed: boolean;
  completed: TourSegment[];
}

export interface Teacher {
  id: number;
  email: string;
  full_name: string;
  school_name: string;
  date_joined: string;
  onboarding?: TeacherOnboarding;
}

export interface ClientConfig {
  public_base_url: string;
  dashboard_poll_seconds: number;
  min_questions: number;
  max_questions: number;
  max_choices: number;
  max_image_bytes: number;
  ai_suggestions_enabled: boolean;
}

export interface QuestionImageUpload {
  id: number;
  /** Same-origin path such as `/media/question-images/<random>.jpg`. */
  url: string;
  width: number;
  height: number;
}

export interface Classroom {
  id: number;
  name: string;
  subject: string;
  level: string;
  academic_period: string;
  is_active: boolean;
  self_enrollment_enabled: boolean;
  invite_token: string;
  class_join_url: string;
  roster_size: number;
  activity_count: number;
  created_at: string;
  updated_at: string;
}

export interface StudentAccount {
  id: number;
  email: string;
  full_name: string;
}

export interface PublicClassInfo {
  name: string;
  subject: string;
  level: string;
  teacher_name: string;
  self_enrollment_enabled: boolean;
}

export interface ClassJoinResult {
  classroom_name: string;
  student_id: number;
  already_enrolled: boolean;
}

export interface ActivityImportResult {
  activity_id: number | null;
  row_errors: { line: number; message: string }[];
}

export interface Student {
  id: number;
  display_name: string;
  school_identifier: string;
  email: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Enrollment {
  id: number;
  classroom: number;
  student: number;
  student_detail: Student;
  is_active: boolean;
  created_at: string;
}

export interface Choice {
  id?: number;
  text: string;
  is_correct: boolean;
  position?: number;
}

export interface Question {
  id?: number;
  position?: number;
  prompt: string;
  /** Omitted = leave the picture alone; `null` = remove it. */
  image_id?: number | null;
  image_url?: string | null;
  image_alt?: string;
  question_type: QuestionType;
  /** Labels for the ends of a 1-5 rating scale (rating questions only). */
  rating_low_label?: string;
  rating_high_label?: string;
  is_required: boolean;
  collect_confidence: boolean;
  accepted_answers: string[];
  choices: Choice[];
  is_auto_scored?: boolean;
  /** How many student answers this saved question already holds. */
  response_count?: number;
}

export interface Activity {
  id: number;
  classroom: number;
  classroom_name: string;
  title: string;
  topic: string;
  status: ActivityStatus;
  kind?: ActivityKind;
  questions: Question[];
  question_count: number;
  open_session_count: number;
  follow_up_of_session: number | null;
  follow_up_of_session_code: string | null;
  created_at: string;
  updated_at: string;
}

export type ActivityListItem = Omit<Activity, 'questions' | 'open_session_count'>;

export interface ActivityWritePayload {
  classroom: number;
  title: string;
  topic: string;
  kind?: ActivityKind;
  status?: ActivityStatus;
  questions: Question[];
}

export interface LiveSession {
  id: number;
  activity: number;
  activity_title: string;
  activity_topic: string;
  classroom: number;
  classroom_name: string;
  code: string;
  public_token: string;
  join_url: string;
  status: SessionStatus;
  identity_mode: IdentityMode;
  activity_kind?: ActivityKind;
  roster_size: number;
  participant_count: number;
  submitted_count: number;
  has_reflection: boolean;
  poll_interval_seconds: number;
  started_at: string;
  closed_at: string | null;
}

export interface ChoiceBreakdown {
  choice_id: number;
  text: string;
  is_correct: boolean;
  count: number;
  percentage: number;
}

export interface CommonAnswer {
  answer: string;
  normalized: string;
  count: number;
  percentage: number;
  matches_accepted: boolean | null;
}

export type ConfidenceDistribution = Record<string, number>;

export interface QuestionInsight {
  question_id: number;
  position: number;
  prompt: string;
  question_type: QuestionType;
  is_auto_scored: boolean;
  response_count: number;
  correct_count: number;
  incorrect_count: number;
  correctness_percentage: number | null;
  choice_breakdown: ChoiceBreakdown[];
  common_answers: CommonAnswer[];
  confidence_distribution: ConfidenceDistribution;
  average_confidence: number | null;
  /** Survey-only: respondents per rating level ("1".."5"). Empty for quizzes. */
  rating_distribution?: Record<string, number>;
  average_rating?: number | null;
  /** Survey-only: every written answer, verbatim. */
  text_answers?: string[];
}

export interface SignalItem {
  participant_id: number;
  label: string;
  question_position: number;
  question_prompt: string;
  confidence_value: number;
}

export interface AttentionItem {
  participant_id: number;
  label: string;
  reasons: string[];
  score_percentage: number | null;
  average_confidence: number | null;
}

export interface LowestCorrectnessQuestion {
  question_id: number;
  position: number;
  prompt: string;
  correctness_percentage: number;
  below_threshold: boolean;
}

/**
 * Deterministic figures. `kind: 'fact'` is the contract the UI relies on to
 * present these differently from AI suggestions.
 */
export interface SessionFacts {
  kind: 'fact';
  session_id: number;
  session_code: string;
  session_status: SessionStatus;
  activity_title: string;
  activity_topic: string;
  classroom_name: string;
  roster_size: number;
  participant_count: number;
  submitted_count: number;
  completion_percentage: number | null;
  auto_scored_response_count: number;
  overall_correctness_percentage: number | null;
  confidence_distribution: ConfidenceDistribution;
  average_confidence: number | null;
  questions: QuestionInsight[];
  lowest_correctness_questions: LowestCorrectnessQuestion[];
  high_confidence_incorrect: SignalItem[];
  low_confidence_correct: SignalItem[];
  needs_attention: AttentionItem[];
  has_confidence_data: boolean;
  has_auto_scored_data: boolean;
  activity_kind?: ActivityKind;
}

/** Advisory output from an insight provider. Never authoritative. */
export interface Suggestion {
  kind: 'suggestion';
  title: string;
  body: string;
  category: 'misconception' | 'follow_up' | 'next_question' | 'summary';
  source: string;
  requires_teacher_review: boolean;
}

export interface MisconceptionFact {
  kind: 'fact';
  label: string;
  value: string | number;
}

export interface MisconceptionSuggestion {
  kind: 'suggestion';
  title: string;
  body: string;
  requires_teacher_review: boolean;
}

export interface MisconceptionCard {
  question_id: number;
  position: number;
  prompt: string;
  question_type: QuestionType;
  correctness_percentage: number;
  high_confidence_wrong_count: number;
  facts: MisconceptionFact[];
  suggestion: MisconceptionSuggestion | null;
}

export interface BaselineSnapshot {
  session_id: number;
  session_code: string;
  closed_at: string | null;
  overall_correctness: number | null;
  primary_gap: string;
  planned_action: string;
}

export interface QuestionDelta {
  source_question_id: number | null;
  baseline_position: number;
  current_position: number;
  baseline_correctness: number | null;
  current_correctness: number | null;
  delta: number | null;
}

export interface StudentMovement {
  improved: { student_id: number; label: string }[];
  still_stuck: { student_id: number; label: string }[];
  improved_count: number;
  still_stuck_count: number;
}

export interface SessionComparison {
  kind: 'fact';
  baseline_snapshot: BaselineSnapshot | null;
  overall_delta: number | null;
  question_deltas: QuestionDelta[];
  alignment: 'full' | 'partial';
  student_movement: StudentMovement | null;
  tracking_mode: 'roster' | 'class_only';
}

export interface TopicTimelineEntry {
  id: number;
  code: string;
  closed_at: string | null;
  correctness: number | null;
  has_reflection: boolean;
  plan_impact: PlanImpact | null;
}

export interface TopicTimelineGroup {
  topic: string;
  sessions: TopicTimelineEntry[];
}

export interface DashboardResponse {
  session: LiveSession;
  facts: SessionFacts;
  suggestions: Suggestion[];
  misconception_cards: MisconceptionCard[];
  comparison: SessionComparison | null;
  poll_interval_seconds: number;
}

export interface ParticipantResponse {
  id: number;
  question: number;
  question_position: number;
  question_prompt: string;
  question_type: QuestionType;
  selected_choice: number | null;
  selected_choice_text: string | null;
  /** Multi-select answers. */
  selected_choice_texts?: string[];
  rating_value?: number | null;
  text_response: string;
  confidence_value: number | null;
  is_correct: boolean | null;
  created_at: string;
}

export interface Participant {
  id: number;
  label: string;
  /** Name or identifier the student entered when joining (always stored). */
  display_name: string;
  student: number | null;
  has_submitted: boolean;
  submitted_at: string | null;
  created_at: string;
  responses: ParticipantResponse[];
}

export interface TeacherReflection {
  id: number;
  live_session: number;
  session_code: string;
  activity_title: string;
  primary_gap: string;
  plan_impact: PlanImpact;
  planned_action: string;
  notes: string;
  created_at: string;
  updated_at: string;
}

export interface SessionResults {
  session: LiveSession;
  facts: SessionFacts;
  suggestions: Suggestion[];
  misconception_cards: MisconceptionCard[];
  comparison: SessionComparison | null;
  participants: Participant[];
  reflection: TeacherReflection | null;
}

export interface RecentResult {
  session: LiveSession;
  activity_kind?: ActivityKind;
  submitted_count: number;
  completion_percentage: number | null;
  overall_correctness_percentage: number | null;
  average_confidence: number | null;
  needs_attention_count: number;
  misconception_count: number;
  has_comparison: boolean;
}

export interface ReviewItem {
  id: number;
  classroom: number;
  classroom_name: string;
  topic_key: string;
  topic_label: string;
  box: number;
  last_score: number | null;
  last_session: number | null;
  last_session_code: string | null;
  due_at: string;
  snoozed_until: string | null;
  is_due: boolean;
  interval_days: number;
  updated_at: string;
}

export interface PendingFollowUp {
  classroom_id: number;
  classroom_name: string;
  topic: string;
  last_session_id: number;
  last_session_code: string;
  closed_at: string | null;
  days_since: number;
  primary_gap: string;
  plan_impact: PlanImpact;
  top_misconception_title: string;
}

export interface TeacherOverview {
  teacher: Pick<Teacher, 'id' | 'full_name' | 'email' | 'school_name'>;
  classrooms: Classroom[];
  recent_activities: ActivityListItem[];
  open_sessions: LiveSession[];
  recent_results: RecentResult[];
  pending_followups: PendingFollowUp[];
  due_reviews?: ReviewItem[];
  counts: {
    classrooms: number;
    activities: number;
    open_sessions: number;
    students: number;
  };
}

export interface RosterImportResult {
  created_students: number;
  updated_students: number;
  created_enrollments: number;
  reactivated_enrollments: number;
  skipped_rows: number;
  row_errors: { line: number; message: string }[];
}

// --------------------------------------------------------------------------
// Public (student) shapes
// --------------------------------------------------------------------------
export interface PublicChoice {
  id: number;
  text: string;
  position: number;
}

/** Note the absence of `is_correct` / `accepted_answers`. */
export interface PublicQuestion {
  id: number;
  position: number;
  prompt: string;
  image_url?: string | null;
  image_alt?: string;
  question_type: QuestionType;
  rating_low_label?: string;
  rating_high_label?: string;
  is_required: boolean;
  collect_confidence: boolean;
  choices: PublicChoice[];
}

export interface PublicSession {
  public_token: string;
  code: string;
  status: SessionStatus;
  is_open: boolean;
  identity_mode: IdentityMode;
  activity_kind?: ActivityKind;
  activity_title: string;
  activity_topic: string;
  class_name: string;
  questions: PublicQuestion[];
  confidence_scale: { min: number; max: number };
}

export interface PublicJoinResult {
  participant_token: string;
  display_label: string;
  resumed: boolean;
  session: PublicSession;
}

export interface PublicAnswer {
  question: number;
  selected_choice?: number | null;
  /** Multi-select: every ticked choice. */
  selected_choices?: number[];
  rating_value?: number | null;
  text_response?: string;
  confidence_value?: number | null;
}

export interface PublicSubmitResult {
  detail: string;
  submitted_at: string;
  answer_count: number;
  activity_title: string;
}

export interface HealthResponse {
  status: string;
  service: string;
  database: string;
  django: string;
  debug: boolean;
}
