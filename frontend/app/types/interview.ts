// Shared Interview Types and Runtime Type Guards for Antigravity Frontend

export type SessionStatus = 'generating' | 'ready' | 'generation_failed' | 'in_progress' | 'completed';
export type QuestionCategory =
  | 'backend_fundamentals'
  | 'cv_project_experience'
  | 'database'
  | 'api_web_design'
  | 'debugging_problem_solving'
  | 'behavioral_teamwork';
export type QuestionDifficulty = 'easy' | 'medium' | 'hard';

export const VALID_SESSION_STATUSES: readonly SessionStatus[] = [
  'generating',
  'ready',
  'generation_failed',
  'in_progress',
  'completed',
] as const;

export const VALID_QUESTION_CATEGORIES: readonly QuestionCategory[] = [
  'backend_fundamentals',
  'cv_project_experience',
  'database',
  'api_web_design',
  'debugging_problem_solving',
  'behavioral_teamwork',
] as const;

export const VALID_QUESTION_DIFFICULTIES: readonly QuestionDifficulty[] = [
  'easy',
  'medium',
  'hard',
] as const;

export const VALID_READINESS_LEVELS: readonly string[] = [
  'needs_foundation',
  'developing',
  'intern_ready',
  'strong_intern_candidate',
] as const;

export const SENSITIVE_FORBIDDEN_KEYS: readonly string[] = [
  'expected_key_points',
  'purpose',
  'source',
  'source_evidence',
  'answer_text',
  'suggested_answer',
  'missing_points',
  'prompt',
] as const;

export function isValidUuid(id: unknown): id is string {
  if (typeof id !== 'string') return false;
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id);
}

export interface InterviewQuestionResponse {
  id: string;
  order_index: number;
  question_text: string;
  category: QuestionCategory;
  difficulty: QuestionDifficulty;
}

export function isInterviewQuestion(data: unknown): data is InterviewQuestionResponse {
  if (!data || typeof data !== 'object') return false;
  const d = data as Record<string, unknown>;

  // Forbidden sensitive keys
  for (const k of ['expected_key_points', 'purpose', 'source', 'source_evidence']) {
    if (k in d) return false;
  }

  if (!isValidUuid(d.id)) return false;
  if (
    typeof d.order_index !== 'number' ||
    !Number.isFinite(d.order_index) ||
    !Number.isInteger(d.order_index) ||
    d.order_index < 1 ||
    d.order_index > 10
  ) {
    return false;
  }
  if (typeof d.question_text !== 'string' || d.question_text.trim() === '') return false;

  if (
    typeof d.category !== 'string' ||
    !VALID_QUESTION_CATEGORIES.includes(d.category as QuestionCategory)
  ) {
    return false;
  }

  if (
    typeof d.difficulty !== 'string' ||
    !VALID_QUESTION_DIFFICULTIES.includes(d.difficulty as QuestionDifficulty)
  ) {
    return false;
  }

  return true;
}

export interface InterviewSessionResponse {
  id: string;
  job_application_id: string;
  attempt_number: number;
  status: SessionStatus;
  provider: string;
  model: string;
  schema_version: string;
  prompt_version: string;
  error_code: string | null;
  error_message: string | null;
  generated_at: string | null;
  questions: InterviewQuestionResponse[];
}

export function isInterviewSessionResponse(
  data: unknown,
  expectedAppId?: string
): data is InterviewSessionResponse {
  if (!data || typeof data !== 'object') return false;
  const d = data as Record<string, unknown>;

  // Forbidden sensitive keys
  for (const k of ['expected_key_points', 'purpose', 'source', 'source_evidence']) {
    if (k in d) return false;
  }

  if (!isValidUuid(d.id) || !isValidUuid(d.job_application_id)) return false;
  if (expectedAppId && d.job_application_id !== expectedAppId) return false;

  if (
    typeof d.attempt_number !== 'number' ||
    !Number.isFinite(d.attempt_number) ||
    !Number.isInteger(d.attempt_number) ||
    d.attempt_number < 1
  ) {
    return false;
  }

  if (
    typeof d.status !== 'string' ||
    !VALID_SESSION_STATUSES.includes(d.status as SessionStatus)
  ) {
    return false;
  }

  // Non-empty string metadata
  if (typeof d.provider !== 'string' || d.provider.trim() === '') return false;
  if (typeof d.model !== 'string' || d.model.trim() === '') return false;
  if (typeof d.schema_version !== 'string' || d.schema_version.trim() === '') return false;
  if (typeof d.prompt_version !== 'string' || d.prompt_version.trim() === '') return false;

  // Required keys check
  if (!('error_code' in d)) return false;
  if (!('error_message' in d)) return false;
  if (!('generated_at' in d)) return false;
  if (!('questions' in d)) return false;

  // error_code and error_message must be string or null
  if (d.error_code !== null && typeof d.error_code !== 'string') return false;
  if (d.error_message !== null && typeof d.error_message !== 'string') return false;

  // generated_at must be non-empty string or null
  if (d.generated_at !== null && (typeof d.generated_at !== 'string' || d.generated_at.trim() === '')) {
    return false;
  }

  // Questions must always be an array
  if (!Array.isArray(d.questions)) return false;
  if (!d.questions.every(isInterviewQuestion)) return false;

  // Special strict requirement when status = ready
  if (d.status === 'ready') {
    if (d.questions.length !== 10) return false;
    // Exactly 1..10 in order
    for (let i = 0; i < 10; i++) {
      if (d.questions[i].order_index !== i + 1) {
        return false;
      }
    }
  }

  return true;
}

export interface InterviewHistoryItem {
  id: string;
  job_application_id: string;
  attempt_number: number;
  status: SessionStatus;
  question_count: number;
  answered_count: number;
  skipped_count: number;
  total_score: number | null;
  average_score: number | null;
  readiness_level: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  evaluated_at: string | null;
}

export function isInterviewHistoryItem(data: unknown): data is InterviewHistoryItem {
  if (!data || typeof data !== 'object') return false;
  const d = data as Record<string, unknown>;

  // Strict check: sensitive keys must not be present
  for (const k of SENSITIVE_FORBIDDEN_KEYS) {
    if (k in d) return false;
  }

  if (!isValidUuid(d.id) || !isValidUuid(d.job_application_id)) return false;

  // attempt_number: finite integer >= 1
  if (
    typeof d.attempt_number !== 'number' ||
    !Number.isFinite(d.attempt_number) ||
    !Number.isInteger(d.attempt_number) ||
    d.attempt_number < 1
  ) {
    return false;
  }

  if (
    typeof d.status !== 'string' ||
    !VALID_SESSION_STATUSES.includes(d.status as SessionStatus)
  ) {
    return false;
  }

  // question_count, answered_count, skipped_count: finite integer in [0, 10]
  const counts = [d.question_count, d.answered_count, d.skipped_count];
  for (const c of counts) {
    if (
      typeof c !== 'number' ||
      !Number.isFinite(c) ||
      !Number.isInteger(c) ||
      c < 0 ||
      c > 10
    ) {
      return false;
    }
  }
  const qCount = d.question_count as number;
  const aCount = d.answered_count as number;
  const sCount = d.skipped_count as number;

  // answered_count + skipped_count cannot exceed question_count
  if (aCount + sCount > qCount) return false;

  // total_score check
  if (d.total_score !== null) {
    if (
      typeof d.total_score !== 'number' ||
      !Number.isFinite(d.total_score) ||
      d.total_score < 0 ||
      d.total_score > 100
    ) {
      return false;
    }
  }

  // average_score check
  if (d.average_score !== null) {
    if (
      typeof d.average_score !== 'number' ||
      !Number.isFinite(d.average_score) ||
      d.average_score < 0 ||
      d.average_score > 10
    ) {
      return false;
    }
  }

  // total_score and average_score must both be null or both have numeric values
  if ((d.total_score === null) !== (d.average_score === null)) {
    return false;
  }

  // readiness_level only allowed when score exists
  if (d.readiness_level !== null) {
    if (d.total_score === null) return false;
    if (
      typeof d.readiness_level !== 'string' ||
      !VALID_READINESS_LEVELS.includes(d.readiness_level)
    ) {
      return false;
    }
  }

  // Timestamps
  if (typeof d.created_at !== 'string' || d.created_at.trim() === '') return false;
  if (d.started_at !== null && (typeof d.started_at !== 'string' || d.started_at.trim() === '')) return false;
  if (d.completed_at !== null && (typeof d.completed_at !== 'string' || d.completed_at.trim() === '')) return false;
  if (d.evaluated_at !== null && (typeof d.evaluated_at !== 'string' || d.evaluated_at.trim() === '')) return false;

  return true;
}

export interface InterviewHistoryListResponse {
  items: InterviewHistoryItem[];
  total: number;
  limit: number;
  offset: number;
}

export function isInterviewHistoryListResponse(data: unknown): data is InterviewHistoryListResponse {
  if (!data || typeof data !== 'object') return false;
  const d = data as Record<string, unknown>;

  // No sensitive keys at root
  for (const k of SENSITIVE_FORBIDDEN_KEYS) {
    if (k in d) return false;
  }

  // total and offset: finite integer >= 0
  if (
    typeof d.total !== 'number' ||
    !Number.isFinite(d.total) ||
    !Number.isInteger(d.total) ||
    d.total < 0
  ) {
    return false;
  }

  if (
    typeof d.offset !== 'number' ||
    !Number.isFinite(d.offset) ||
    !Number.isInteger(d.offset) ||
    d.offset < 0
  ) {
    return false;
  }

  // limit: finite integer in [1, 50]
  if (
    typeof d.limit !== 'number' ||
    !Number.isFinite(d.limit) ||
    !Number.isInteger(d.limit) ||
    d.limit < 1 ||
    d.limit > 50
  ) {
    return false;
  }

  if (!Array.isArray(d.items)) return false;
  if (d.items.length > d.limit) return false;
  if (!d.items.every(isInterviewHistoryItem)) return false;

  return true;
}
