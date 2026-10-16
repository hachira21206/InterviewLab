// Shared Interview Progress Types and Strict Type Guards for Task 09

import { isValidUuid, VALID_QUESTION_CATEGORIES, VALID_READINESS_LEVELS, QuestionCategory } from './interview';

export type ComparisonStatus = 'no_data' | 'insufficient_data' | 'improved' | 'declined' | 'unchanged';
export type ReadinessDirection = 'improved' | 'declined' | 'unchanged';

export const VALID_COMPARISON_STATUSES: readonly ComparisonStatus[] = [
  'no_data',
  'insufficient_data',
  'improved',
  'declined',
  'unchanged',
] as const;

export const VALID_READINESS_DIRECTIONS: readonly ReadinessDirection[] = [
  'improved',
  'declined',
  'unchanged',
] as const;

export const SENSITIVE_PROGRESS_FORBIDDEN_KEYS: readonly string[] = [
  'expected_key_points',
  'purpose',
  'source',
  'source_evidence',
  'question_text',
  'answer_text',
  'suggested_answer',
  'feedback',
  'missing_points',
  'prompt',
  'extracted_text',
  'job_description',
] as const;

export interface InterviewProgressTrendItem {
  session_id: string;
  attempt_number: number;
  total_score: number;
  average_score: number;
  answered_count: number;
  skipped_count: number;
  readiness_level: string;
  category_scores: Record<string, number>;
  completed_at: string | null;
  evaluated_at: string | null;
}

export interface InterviewProgressLatestItem {
  session_id: string;
  attempt_number: number;
  total_score: number;
  average_score: number;
  readiness_level: string;
}

export interface InterviewProgressDelta {
  total_score_delta: number;
  average_score_delta: number;
  answered_count_delta: number;
  skipped_count_delta: number;
  readiness_changed: boolean;
  readiness_direction: ReadinessDirection;
}

export interface InterviewProgressComparison {
  status: ComparisonStatus;
  latest_vs_previous: InterviewProgressDelta | null;
  latest_vs_first: InterviewProgressDelta | null;
}

export interface CategoryProgressItem {
  category: QuestionCategory;
  first_score: number;
  previous_score: number | null;
  latest_score: number;
  latest_vs_previous_delta: number | null;
  latest_vs_first_delta: number | null;
  attempts_with_data: number;
}

export interface InterviewProgressReportResponse {
  job_application_id: string;
  total_attempts: number;
  completed_attempts: number;
  evaluated_attempts: number;
  trend: InterviewProgressTrendItem[];
  latest: InterviewProgressLatestItem | null;
  comparison: InterviewProgressComparison;
  category_progress: CategoryProgressItem[];
}

function hasSensitiveForbiddenKeys(obj: unknown): boolean {
  if (!obj || typeof obj !== 'object') return false;
  const d = obj as Record<string, unknown>;
  for (const key of Object.keys(d)) {
    if (SENSITIVE_PROGRESS_FORBIDDEN_KEYS.includes(key)) return true;
    if (d[key] && typeof d[key] === 'object') {
      if (hasSensitiveForbiddenKeys(d[key])) return true;
    }
  }
  return false;
}

export const READINESS_RANKS: Record<string, number> = {
  needs_foundation: 1,
  developing: 2,
  intern_ready: 3,
  strong_intern_candidate: 4,
};

/**
 * Safely convert a numeric score to integer cents using ROUND_HALF_UP.
 * Uses string/fixed precision to avoid IEEE-754 binary floating-point inaccuracies
 * (e.g. 1.005 * 100 becoming 100.49999999999999).
 */
export function toRoundedCents(value: number): number {
  if (typeof value !== 'number' || !Number.isFinite(value) || Number.isNaN(value)) {
    throw new Error('Invalid numeric value: not finite');
  }
  const sign = value < 0 ? -1 : 1;
  const abs = Math.abs(value);
  const parts = abs.toFixed(6).split('.');
  const intPart = parts[0];
  const decPart = parts[1];
  const centsStr = intPart + decPart.slice(0, 2);
  const thirdDigit = parseInt(decPart[2], 10);
  let cents = parseInt(centsStr, 10);
  if (thirdDigit >= 5) cents += 1;
  return sign * cents;
}

/**
 * Round a number to 2 decimal places using ROUND_HALF_UP semantics.
 */
export function round2(value: number): number {
  return toRoundedCents(value) / 100;
}

/**
 * Compare two numbers for exact equality in cents (2 decimal places) using ROUND_HALF_UP.
 */
export function isSameRounded2(a: number, b: number): boolean {
  if (typeof a !== 'number' || typeof b !== 'number') return false;
  if (!Number.isFinite(a) || !Number.isFinite(b)) return false;
  return toRoundedCents(a) === toRoundedCents(b);
}

/**
 * Compute average score (totalScore / count) rounded to 2 decimal places (ROUND_HALF_UP).
 * Guarantees 100% precision match with Python Decimal ROUND_HALF_UP.
 */
export function roundAverage2(totalScore: number, count: number = 10): number {
  if (!Number.isFinite(totalScore) || !Number.isFinite(count) || count <= 0) {
    throw new Error('Invalid arguments for roundAverage2');
  }
  const sign = totalScore < 0 ? -1 : 1;
  const abs = Math.abs(totalScore);
  const totalCents = toRoundedCents(abs);
  const rem = totalCents % count;
  let q = Math.floor(totalCents / count);
  if (rem * 2 >= count) {
    q += 1;
  }
  return sign * (q / 100);
}

/**
 * Compute delta between two scores (current - base) rounded to 2 decimal places.
 */
export function roundDelta2(current: number, base: number): number {
  const curCents = toRoundedCents(current);
  const baseCents = toRoundedCents(base);
  return (curCents - baseCents) / 100;
}

/**
 * Safely compute average of an array of numeric scores using integer cents arithmetic.
 */
export function roundAverageScores(scores: number[]): number {
  if (!Array.isArray(scores) || scores.length === 0) {
    throw new Error('Cannot compute average of empty score list');
  }
  let totalCents = 0;
  for (const s of scores) {
    totalCents += toRoundedCents(s);
  }
  const count = scores.length;
  const rem = Math.abs(totalCents) % count;
  let q = Math.floor(Math.abs(totalCents) / count);
  if (rem * 2 >= count) q += 1;
  const sign = totalCents < 0 ? -1 : 1;
  return sign * (q / 100);
}

function verifyComparisonDelta(
  delta: InterviewProgressDelta,
  latestItem: InterviewProgressTrendItem,
  targetItem: InterviewProgressTrendItem
): boolean {
  const expectedTotalDelta = roundDelta2(latestItem.total_score, targetItem.total_score);
  if (!isSameRounded2(delta.total_score_delta, expectedTotalDelta)) return false;

  const expectedAvgDelta = roundDelta2(latestItem.average_score, targetItem.average_score);
  if (!isSameRounded2(delta.average_score_delta, expectedAvgDelta)) return false;

  if (delta.answered_count_delta !== latestItem.answered_count - targetItem.answered_count) return false;
  if (delta.skipped_count_delta !== latestItem.skipped_count - targetItem.skipped_count) return false;

  const expectedChanged = latestItem.readiness_level !== targetItem.readiness_level;
  if (delta.readiness_changed !== expectedChanged) return false;

  const latestRank = READINESS_RANKS[latestItem.readiness_level] ?? 0;
  const targetRank = READINESS_RANKS[targetItem.readiness_level] ?? 0;
  let expectedDirection: ReadinessDirection;
  if (latestRank > targetRank) {
    expectedDirection = 'improved';
  } else if (latestRank < targetRank) {
    expectedDirection = 'declined';
  } else {
    expectedDirection = 'unchanged';
  }
  if (delta.readiness_direction !== expectedDirection) return false;

  return true;
}

export function isInterviewProgressTrendItem(data: unknown): data is InterviewProgressTrendItem {
  if (!data || typeof data !== 'object') return false;
  const d = data as Record<string, unknown>;

  if (!isValidUuid(d.session_id)) return false;
  if (typeof d.attempt_number !== 'number' || !Number.isInteger(d.attempt_number) || d.attempt_number < 1) return false;
  if (typeof d.total_score !== 'number' || !Number.isFinite(d.total_score) || d.total_score < 0 || d.total_score > 100) return false;
  if (typeof d.average_score !== 'number' || !Number.isFinite(d.average_score) || d.average_score < 0 || d.average_score > 10) return false;

  // Consistency check: average_score must equal roundAverage2(total_score, 10)
  const expectedAverage = roundAverage2(d.total_score, 10);
  if (!isSameRounded2(d.average_score, expectedAverage)) return false;

  if (typeof d.answered_count !== 'number' || !Number.isInteger(d.answered_count) || d.answered_count < 0 || d.answered_count > 10) return false;
  if (typeof d.skipped_count !== 'number' || !Number.isInteger(d.skipped_count) || d.skipped_count < 0 || d.skipped_count > 10) return false;
  if (d.answered_count + d.skipped_count !== 10) return false;

  if (typeof d.readiness_level !== 'string' || !VALID_READINESS_LEVELS.includes(d.readiness_level)) return false;

  if (!d.category_scores || typeof d.category_scores !== 'object' || Array.isArray(d.category_scores)) return false;
  const catScores = d.category_scores as Record<string, unknown>;
  for (const [k, v] of Object.entries(catScores)) {
    if (!VALID_QUESTION_CATEGORIES.includes(k as QuestionCategory)) return false;
    if (typeof v !== 'number' || !Number.isFinite(v) || v < 0 || v > 10) return false;
  }

  if (d.completed_at !== null && (typeof d.completed_at !== 'string' || d.completed_at.trim() === '')) return false;
  if (d.evaluated_at !== null && (typeof d.evaluated_at !== 'string' || d.evaluated_at.trim() === '')) return false;

  return true;
}

export function isInterviewProgressLatestItem(data: unknown): data is InterviewProgressLatestItem {
  if (!data || typeof data !== 'object') return false;
  const d = data as Record<string, unknown>;

  if (!isValidUuid(d.session_id)) return false;
  if (typeof d.attempt_number !== 'number' || !Number.isInteger(d.attempt_number) || d.attempt_number < 1) return false;
  if (typeof d.total_score !== 'number' || !Number.isFinite(d.total_score) || d.total_score < 0 || d.total_score > 100) return false;
  if (typeof d.average_score !== 'number' || !Number.isFinite(d.average_score) || d.average_score < 0 || d.average_score > 10) return false;
  if (typeof d.readiness_level !== 'string' || !VALID_READINESS_LEVELS.includes(d.readiness_level)) return false;

  return true;
}

export function isInterviewProgressDelta(data: unknown): data is InterviewProgressDelta {
  if (!data || typeof data !== 'object') return false;
  const d = data as Record<string, unknown>;

  if (typeof d.total_score_delta !== 'number' || !Number.isFinite(d.total_score_delta)) return false;
  if (typeof d.average_score_delta !== 'number' || !Number.isFinite(d.average_score_delta)) return false;
  if (typeof d.answered_count_delta !== 'number' || !Number.isInteger(d.answered_count_delta)) return false;
  if (typeof d.skipped_count_delta !== 'number' || !Number.isInteger(d.skipped_count_delta)) return false;
  if (typeof d.readiness_changed !== 'boolean') return false;
  if (typeof d.readiness_direction !== 'string' || !VALID_READINESS_DIRECTIONS.includes(d.readiness_direction as ReadinessDirection)) return false;

  return true;
}

export function isCategoryProgressItem(data: unknown): data is CategoryProgressItem {
  if (!data || typeof data !== 'object') return false;
  const d = data as Record<string, unknown>;

  if (typeof d.category !== 'string' || !VALID_QUESTION_CATEGORIES.includes(d.category as QuestionCategory)) return false;
  if (typeof d.first_score !== 'number' || !Number.isFinite(d.first_score) || d.first_score < 0 || d.first_score > 10) return false;
  if (d.previous_score !== null && (typeof d.previous_score !== 'number' || !Number.isFinite(d.previous_score) || d.previous_score < 0 || d.previous_score > 10)) return false;
  if (typeof d.latest_score !== 'number' || !Number.isFinite(d.latest_score) || d.latest_score < 0 || d.latest_score > 10) return false;

  if (d.latest_vs_previous_delta !== null && (typeof d.latest_vs_previous_delta !== 'number' || !Number.isFinite(d.latest_vs_previous_delta))) return false;
  if (d.latest_vs_first_delta !== null && (typeof d.latest_vs_first_delta !== 'number' || !Number.isFinite(d.latest_vs_first_delta))) return false;

  if (typeof d.attempts_with_data !== 'number' || !Number.isInteger(d.attempts_with_data) || d.attempts_with_data < 1) return false;

  if (d.attempts_with_data === 1) {
    if (d.previous_score !== null) return false;
    if (d.latest_vs_previous_delta !== null) return false;
    if (d.latest_vs_first_delta !== null) return false;
  } else {
    if (d.previous_score === null) return false;
    if (d.latest_vs_previous_delta === null) return false;
    if (d.latest_vs_first_delta === null) return false;
  }

  return true;
}

export function isInterviewProgressReportResponse(
  data: unknown,
  expectedApplicationId: unknown
): data is InterviewProgressReportResponse {
  if (!isValidUuid(expectedApplicationId)) return false;
  if (!data || typeof data !== 'object') return false;
  if (hasSensitiveForbiddenKeys(data)) return false;

  const d = data as Record<string, unknown>;

  // Key presence
  if (
    !('job_application_id' in d) ||
    !('total_attempts' in d) ||
    !('completed_attempts' in d) ||
    !('evaluated_attempts' in d) ||
    !('trend' in d) ||
    !('latest' in d) ||
    !('comparison' in d) ||
    !('category_progress' in d)
  ) {
    return false;
  }

  if (!isValidUuid(d.job_application_id)) return false;
  if (d.job_application_id !== expectedApplicationId) return false;

  // Attempt counts
  if (typeof d.total_attempts !== 'number' || !Number.isInteger(d.total_attempts) || d.total_attempts < 0) return false;
  if (typeof d.completed_attempts !== 'number' || !Number.isInteger(d.completed_attempts) || d.completed_attempts < 0) return false;
  if (typeof d.evaluated_attempts !== 'number' || !Number.isInteger(d.evaluated_attempts) || d.evaluated_attempts < 0) return false;
  if (d.completed_attempts > d.total_attempts) return false;
  if (d.evaluated_attempts > d.completed_attempts) return false;

  // Trend validation
  if (!Array.isArray(d.trend)) return false;
  if (d.trend.length !== d.evaluated_attempts) return false;

  const seenSessionIds = new Set<string>();
  const seenAttemptNumbers = new Set<number>();
  let lastAttemptNumber = 0;

  for (const item of d.trend) {
    if (!isInterviewProgressTrendItem(item)) return false;
    if (seenSessionIds.has(item.session_id)) return false;
    seenSessionIds.add(item.session_id);

    if (seenAttemptNumbers.has(item.attempt_number)) return false;
    seenAttemptNumbers.add(item.attempt_number);

    // Trend must be strictly ascending by attempt_number
    if (item.attempt_number <= lastAttemptNumber) return false;
    lastAttemptNumber = item.attempt_number;
  }

  // Latest validation
  if (d.evaluated_attempts === 0) {
    if (d.latest !== null) return false;
  } else {
    if (!isInterviewProgressLatestItem(d.latest)) return false;
    const lastTrendItem = d.trend[d.trend.length - 1];
    if (
      d.latest.session_id !== lastTrendItem.session_id ||
      d.latest.attempt_number !== lastTrendItem.attempt_number ||
      !isSameRounded2(d.latest.total_score, lastTrendItem.total_score) ||
      !isSameRounded2(d.latest.average_score, lastTrendItem.average_score) ||
      d.latest.readiness_level !== lastTrendItem.readiness_level
    ) {
      return false;
    }
  }

  // Comparison validation
  if (!d.comparison || typeof d.comparison !== 'object') return false;
  const comp = d.comparison as Record<string, unknown>;
  if (typeof comp.status !== 'string' || !VALID_COMPARISON_STATUSES.includes(comp.status as ComparisonStatus)) return false;

  if (d.evaluated_attempts === 0) {
    if (comp.status !== 'no_data') return false;
    if (comp.latest_vs_previous !== null || comp.latest_vs_first !== null) return false;
  } else if (d.evaluated_attempts === 1) {
    if (comp.status !== 'insufficient_data') return false;
    if (comp.latest_vs_previous !== null || comp.latest_vs_first !== null) return false;
  } else {
    if (!['improved', 'declined', 'unchanged'].includes(comp.status)) return false;
    if (!isInterviewProgressDelta(comp.latest_vs_previous)) return false;
    if (!isInterviewProgressDelta(comp.latest_vs_first)) return false;

    // Cross-verify deltas against trend data (tolerance < 0.01)
    const latestItem = d.trend[d.trend.length - 1];
    const prevItem = d.trend[d.trend.length - 2];
    const firstItem = d.trend[0];

    if (!verifyComparisonDelta(comp.latest_vs_previous, latestItem, prevItem)) return false;
    if (!verifyComparisonDelta(comp.latest_vs_first, latestItem, firstItem)) return false;

    // Verify comparison.status aligns with delta
    const expectedPrevTotalDelta = roundDelta2(latestItem.total_score, prevItem.total_score);
    const deltaCents = toRoundedCents(expectedPrevTotalDelta);
    if (deltaCents >= 1 && comp.status !== 'improved') return false;
    if (deltaCents <= -1 && comp.status !== 'declined') return false;
    if (deltaCents === 0 && comp.status !== 'unchanged') return false;
  }

  // Category progress validation: rebuild expected category data from trend
  const catScoresMap = new Map<QuestionCategory, number[]>();
  for (const item of d.trend) {
    for (const [cat, score] of Object.entries(item.category_scores)) {
      const qCat = cat as QuestionCategory;
      if (!VALID_QUESTION_CATEGORIES.includes(qCat)) return false;
      if (!catScoresMap.has(qCat)) {
        catScoresMap.set(qCat, []);
      }
      if (typeof score !== 'number' || !Number.isFinite(score)) return false;
      catScoresMap.get(qCat)!.push(score);
    }
  }

  if (!Array.isArray(d.category_progress)) return false;
  // Category progress must contain exactly the union of categories appearing in trend
  if (d.category_progress.length !== catScoresMap.size) return false;

  const seenCategories = new Set<string>();
  for (const catItem of d.category_progress) {
    if (!isCategoryProgressItem(catItem)) return false;
    if (seenCategories.has(catItem.category)) return false;
    seenCategories.add(catItem.category);

    const scores = catScoresMap.get(catItem.category);
    if (!scores || scores.length === 0) return false;

    if (catItem.attempts_with_data !== scores.length) return false;

    const expectedFirst = round2(scores[0]);
    if (!isSameRounded2(catItem.first_score, expectedFirst)) return false;

    const expectedLatest = round2(scores[scores.length - 1]);
    if (!isSameRounded2(catItem.latest_score, expectedLatest)) return false;

    if (scores.length === 1) {
      if (catItem.previous_score !== null) return false;
      if (catItem.latest_vs_previous_delta !== null) return false;
      if (catItem.latest_vs_first_delta !== null) return false;
    } else {
      if (catItem.previous_score === null) return false;
      if (catItem.latest_vs_previous_delta === null) return false;
      if (catItem.latest_vs_first_delta === null) return false;

      const expectedPrev = round2(scores[scores.length - 2]);
      if (!isSameRounded2(catItem.previous_score, expectedPrev)) return false;

      const expectedPrevDelta = roundDelta2(expectedLatest, expectedPrev);
      if (!isSameRounded2(catItem.latest_vs_previous_delta, expectedPrevDelta)) return false;

      const expectedFirstDelta = roundDelta2(expectedLatest, expectedFirst);
      if (!isSameRounded2(catItem.latest_vs_first_delta, expectedFirstDelta)) return false;
    }
  }

  return true;
}
