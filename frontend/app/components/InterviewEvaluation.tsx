'use client';

import Link from 'next/link';
import { useState, useEffect, useRef } from 'react';
import { isSameRounded2, roundAverage2, toRoundedCents, roundAverageScores } from '../types/progress';

type EvaluationStatus = 'pending' | 'evaluating' | 'evaluated' | 'evaluation_failed';
type ReadinessLevel = 'needs_foundation' | 'developing' | 'intern_ready' | 'strong_intern_candidate';
type EvaluationConfidence = 'low' | 'medium' | 'high';

interface ResponseEvaluationDetail {
  interview_response_id: string;
  question_order: number;
  question_text: string;
  category: string;
  difficulty: string;
  is_skipped: boolean;
  technical_accuracy: number;
  completeness: number;
  reasoning_clarity: number;
  relevance: number;
  practical_example: number;
  total_score: number;
  feedback: string;
  strengths: string[];
  missing_points: string[];
  suggested_answer: string;
  study_topics: string[];
  confidence: EvaluationConfidence;
}

interface InterviewEvaluationResponse {
  id: string;
  interview_session_id: string;
  status: EvaluationStatus;
  provider: string;
  model: string;
  prompt_version: string;
  schema_version: string;
  total_score?: number | null;
  average_score?: number | null;
  answered_count?: number | null;
  skipped_count?: number | null;
  category_scores?: Record<string, number> | null;
  overall_summary?: string | null;
  key_strengths?: string[] | null;
  knowledge_gaps?: string[] | null;
  priority_improvements?: string[] | null;
  recommended_study_topics?: string[] | null;
  short_term_study_plan?: string[] | null;
  next_interview_advice?: string | null;
  readiness_level?: ReadinessLevel | null;
  responses: ResponseEvaluationDetail[];
  error_code?: string | null;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
  evaluated_at?: string | null;
}

const UUID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const VALID_CATEGORIES = [
  'backend_fundamentals',
  'cv_experience',
  'database',
  'system_design',
  'debugging',
  'behavioral',
];
const VALID_DIFFICULTIES = ['easy', 'medium', 'hard'];
const VALID_CONFIDENCES = ['low', 'medium', 'high'];

function isApiError(value: unknown): value is { detail: string } {
  if (!value || typeof value !== 'object') return false;
  return typeof (value as Record<string, unknown>).detail === 'string';
}

function isScoreValid(val: unknown, min: number, max: number): val is number {
  return typeof val === 'number' && Number.isFinite(val) && !Number.isNaN(val) && val >= min && val <= max;
}

function isResponseEvaluationDetail(data: unknown): data is ResponseEvaluationDetail {
  if (!data || typeof data !== 'object') return false;
  const d = data as Record<string, unknown>;

  if (typeof d.interview_response_id !== 'string' || !UUID_REGEX.test(d.interview_response_id)) return false;
  if (typeof d.question_order !== 'number' || !Number.isInteger(d.question_order) || d.question_order < 1 || d.question_order > 10) return false;
  if (typeof d.question_text !== 'string' || d.question_text.trim().length === 0) return false;
  if (typeof d.category !== 'string' || !VALID_CATEGORIES.includes(d.category)) return false;
  if (typeof d.difficulty !== 'string' || !VALID_DIFFICULTIES.includes(d.difficulty)) return false;
  if (typeof d.is_skipped !== 'boolean') return false;

  if (d.is_skipped) {
    if (d.total_score !== 0 || d.technical_accuracy !== 0 || d.completeness !== 0 || d.reasoning_clarity !== 0 || d.relevance !== 0 || d.practical_example !== 0) {
      return false;
    }
  } else {
    if (!isScoreValid(d.technical_accuracy, 0, 4)) return false;
    if (!isScoreValid(d.completeness, 0, 2)) return false;
    if (!isScoreValid(d.reasoning_clarity, 0, 2)) return false;
    if (!isScoreValid(d.relevance, 0, 1)) return false;
    if (!isScoreValid(d.practical_example, 0, 1)) return false;
    if (!isScoreValid(d.total_score, 0, 10)) return false;

    const sumCents =
      toRoundedCents(d.technical_accuracy as number) +
      toRoundedCents(d.completeness as number) +
      toRoundedCents(d.reasoning_clarity as number) +
      toRoundedCents(d.relevance as number) +
      toRoundedCents(d.practical_example as number);
    if (!isSameRounded2(d.total_score as number, sumCents / 100)) return false;
  }

  if (typeof d.confidence !== 'string' || !VALID_CONFIDENCES.includes(d.confidence)) return false;
  if (typeof d.feedback !== 'string' || d.feedback.trim().length === 0) return false;
  if (!Array.isArray(d.strengths) || !d.strengths.every(s => typeof s === 'string')) return false;
  if (!Array.isArray(d.missing_points) || !d.missing_points.every(s => typeof s === 'string')) return false;
  if (typeof d.suggested_answer !== 'string' || d.suggested_answer.trim().length === 0) return false;
  if (!Array.isArray(d.study_topics) || !d.study_topics.every(s => typeof s === 'string')) return false;

  return true;
}

function isInterviewEvaluationResponse(data: unknown): data is InterviewEvaluationResponse {
  if (!data || typeof data !== 'object') return false;
  const d = data as Record<string, unknown>;

  if (typeof d.id !== 'string' || !UUID_REGEX.test(d.id)) return false;
  if (typeof d.interview_session_id !== 'string' || !UUID_REGEX.test(d.interview_session_id)) return false;
  if (typeof d.status !== 'string' || !['pending', 'evaluating', 'evaluated', 'evaluation_failed'].includes(d.status)) return false;

  // Check mandatory metadata fields
  if (typeof d.provider !== 'string' || d.provider.trim().length === 0) return false;
  if (typeof d.model !== 'string' || d.model.trim().length === 0) return false;
  if (typeof d.prompt_version !== 'string' || d.prompt_version.trim().length === 0) return false;
  if (typeof d.schema_version !== 'string' || d.schema_version.trim().length === 0) return false;
  if (typeof d.created_at !== 'string' || d.created_at.trim().length === 0) return false;
  if (typeof d.updated_at !== 'string' || d.updated_at.trim().length === 0) return false;
  if (d.evaluated_at !== undefined && d.evaluated_at !== null && typeof d.evaluated_at !== 'string') return false;

  if (d.status === 'evaluated') {
    if (!isScoreValid(d.total_score, 0, 100)) return false;
    if (!isScoreValid(d.average_score, 0, 10)) return false;

    if (
      typeof d.answered_count !== 'number' ||
      !Number.isInteger(d.answered_count) ||
      d.answered_count < 0 ||
      d.answered_count > 10 ||
      typeof d.skipped_count !== 'number' ||
      !Number.isInteger(d.skipped_count) ||
      d.skipped_count < 0 ||
      d.skipped_count > 10 ||
      d.answered_count + d.skipped_count !== 10
    ) {
      return false;
    }

    if (!Array.isArray(d.responses) || d.responses.length !== 10) return false;
    if (!d.responses.every(isResponseEvaluationDetail)) return false;

    const orders = d.responses.map(r => r.question_order);
    for (let i = 0; i < 10; i++) {
      if (orders[i] !== i + 1) return false;
    }

    const actualAnswered = d.responses.filter(r => !r.is_skipped).length;
    const actualSkipped = d.responses.filter(r => r.is_skipped).length;
    if (d.answered_count !== actualAnswered || d.skipped_count !== actualSkipped) return false;

    const totalSumCents = d.responses.reduce((acc, r) => acc + toRoundedCents(r.total_score), 0);
    if (!isSameRounded2(d.total_score as number, totalSumCents / 100)) return false;
    const expectedAvg = roundAverage2(d.total_score as number, 10);
    if (!isSameRounded2(d.average_score as number, expectedAvg)) return false;

    if (!d.category_scores || typeof d.category_scores !== 'object' || Array.isArray(d.category_scores)) return false;
    const catScores = d.category_scores as Record<string, unknown>;

    // Exact category keys check
    const catMap: Record<string, number[]> = {};
    for (const r of d.responses) {
      if (!catMap[r.category]) catMap[r.category] = [];
      catMap[r.category].push(r.total_score);
    }
    const actualCategories = Object.keys(catMap);
    const scoreCategories = Object.keys(catScores);

    if (actualCategories.length !== scoreCategories.length) return false;
    for (const cat of scoreCategories) {
      if (!catMap[cat]) return false; // reject extra category
      const score = catScores[cat];
      if (typeof score !== 'number' || !Number.isFinite(score) || Number.isNaN(score) || score < 0 || score > 10) {
        return false;
      }
      const expectedCatAvg = roundAverageScores(catMap[cat]);
      if (!isSameRounded2(score, expectedCatAvg)) return false;
    }

    let expectedLevel: ReadinessLevel;
    if ((d.total_score as number) < 50) expectedLevel = 'needs_foundation';
    else if ((d.total_score as number) < 70) expectedLevel = 'developing';
    else if ((d.total_score as number) < 85) expectedLevel = 'intern_ready';
    else expectedLevel = 'strong_intern_candidate';
    if (d.readiness_level !== expectedLevel) return false;

    if (typeof d.overall_summary !== 'string' || d.overall_summary.trim().length === 0) return false;
    if (typeof d.next_interview_advice !== 'string' || d.next_interview_advice.trim().length === 0) return false;

    if (!Array.isArray(d.key_strengths) || !d.key_strengths.every(s => typeof s === 'string')) return false;
    if (!Array.isArray(d.knowledge_gaps) || !d.knowledge_gaps.every(s => typeof s === 'string')) return false;
    if (!Array.isArray(d.priority_improvements) || !d.priority_improvements.every(s => typeof s === 'string')) return false;
    if (!Array.isArray(d.recommended_study_topics) || !d.recommended_study_topics.every(s => typeof s === 'string')) return false;
    if (!Array.isArray(d.short_term_study_plan) || !d.short_term_study_plan.every(s => typeof s === 'string')) return false;
  }

  return true;
}

interface InterviewEvaluationProps {
  sessionId: string;
  attemptNumber?: number;
  userAnswers?: Record<number, string | null>;
  showCompletionLinks?: boolean;
}

export default function InterviewEvaluation({
  sessionId,
  attemptNumber,
  userAnswers,
  showCompletionLinks = false,
}: InterviewEvaluationProps) {
  const [evaluation, setEvaluation] = useState<InterviewEvaluationResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [consent, setConsent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);
  const [expandAll, setExpandAll] = useState(false);
  const [exportingDocx, setExportingDocx] = useState(false);
  const [exportNotice, setExportNotice] = useState<string | null>(null);

  const isMountedRef = useRef(true);
  const abortControllerRef = useRef<AbortController | null>(null);

  const getBackendUrl = () => {
    let url = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
    if (url.endsWith('/')) url = url.slice(0, -1);
    return url;
  };

  useEffect(() => {
    isMountedRef.current = true;
    const controller = new AbortController();
    abortControllerRef.current = controller;

    const fetchEvaluation = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(`${getBackendUrl()}/api/v1/interview-sessions/${sessionId}/evaluation`, {
          signal: controller.signal,
        });

        if (res.status === 404) {
          if (isMountedRef.current) {
            setEvaluation(null);
            setLoading(false);
          }
          return;
        }

        const contentType = res.headers.get('content-type') || '';
        if (!contentType.includes('application/json')) {
          if (isMountedRef.current) {
            setError('Dữ liệu trả về từ máy chủ không hợp lệ.');
            setLoading(false);
          }
          return;
        }

        const data = await res.json();
        if (res.ok) {
          if (isInterviewEvaluationResponse(data)) {
            if (isMountedRef.current) {
              setEvaluation(data);
              setError(null);
            }
          } else {
            if (isMountedRef.current) {
              setError('Dữ liệu kết quả đánh giá không đúng định dạng chuẩn.');
            }
          }
        } else {
          if (isMountedRef.current) {
            if (isApiError(data)) {
              setError(data.detail);
            } else {
              setError('Không thể tải kết quả đánh giá.');
            }
          }
        }
      } catch (err: unknown) {
        if ((err as Error)?.name !== 'AbortError') {
          if (isMountedRef.current) {
            setError('Lỗi kết nối khi tải báo cáo đánh giá.');
          }
        }
      } finally {
        if (isMountedRef.current) {
          setLoading(false);
        }
      }
    };

    fetchEvaluation();

    return () => {
      isMountedRef.current = false;
      controller.abort();
    };
  }, [sessionId]);

  const handleEvaluate = async () => {
    if (submitting || !consent) return;

    setSubmitting(true);
    setError(null);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const res = await fetch(`${getBackendUrl()}/api/v1/interview-sessions/${sessionId}/evaluation`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ consent_to_external_ai: true }),
        signal: controller.signal,
      });

      const contentType = res.headers.get('content-type') || '';
      if (!contentType.includes('application/json')) {
        if (isMountedRef.current) {
          setError(`Máy chủ phản hồi với định dạng không hợp lệ (HTTP ${res.status}).`);
          setSubmitting(false);
        }
        return;
      }

      const data = await res.json();
      if (res.ok) {
        if (isInterviewEvaluationResponse(data)) {
          if (isMountedRef.current) {
            setEvaluation(data);
            if (data.status === 'evaluation_failed') {
              setError(data.error_message || 'Quá trình đánh giá thất bại. Vui lòng thử lại.');
            } else {
              setError(null);
            }
          }
        } else {
          if (isMountedRef.current) {
            setError('Dữ liệu kết quả trả về không hợp lệ.');
          }
        }
      } else {
        if (isMountedRef.current) {
          if (isApiError(data)) {
            setError(data.detail);
          } else {
            setError(`Không thể thực hiện đánh giá (Mã lỗi: ${res.status}).`);
          }
        }
      }
    } catch (err: unknown) {
      if ((err as Error)?.name !== 'AbortError') {
        if (isMountedRef.current) {
          setError('Lỗi kết nối mạng khi gửi yêu cầu đánh giá.');
        }
      }
    } finally {
      if (isMountedRef.current) {
        setSubmitting(false);
      }
    }
  };

  const getReadinessBadge = (level?: ReadinessLevel | null) => {
    switch (level) {
      case 'strong_intern_candidate':
        return {
          text: 'Ứng viên Intern xuất sắc',
          className: 'bg-blue-100 text-blue-900 border-blue-300',
        };
      case 'intern_ready':
        return {
          text: 'Sẵn sàng làm Intern',
          className: 'bg-emerald-100 text-emerald-900 border-emerald-300',
        };
      case 'developing':
        return {
          text: 'Đang phát triển',
          className: 'bg-amber-100 text-amber-900 border-amber-300',
        };
      case 'needs_foundation':
      default:
        return {
          text: 'Cần củng cố nền tảng',
          className: 'bg-red-100 text-red-800 border-red-300',
        };
    }
  };

  const escapeHtml = (str: string) =>
    str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');

  const handleDownloadDocx = async () => {
    if (exportingDocx) return;
    setExportingDocx(true);
    setError(null);
    setExportNotice(null);
    try {
      const res = await fetch(`${getBackendUrl()}/api/v1/interview-sessions/${sessionId}/evaluation/export-docx`);
      if (!res.ok) {
        setError(`Không thể xuất file Word (HTTP ${res.status}).`);
        return;
      }
      const blob = await res.blob();
      const disposition = res.headers.get('Content-Disposition') || '';
      const match = disposition.match(/filename="?([^"]+)"?/i);
      const filename = match?.[1] || `Bao_Cao_Phong_Van_${sessionId.slice(0, 8)}.docx`;
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      setExportNotice(`Đã bắt đầu tải ${filename}`);
    } catch {
      setError('Lỗi kết nối khi tải báo cáo Word (.docx).');
    } finally {
      if (isMountedRef.current) {
        setExportingDocx(false);
      }
    }
  };

  const handleExportPdf = () => {
    if (!evaluation || evaluation.status !== 'evaluated') return;
    setExportNotice('Cửa sổ in đã mở. Chọn “Save as PDF” để lưu báo cáo PDF.');
    const badge = getReadinessBadge(evaluation.readiness_level);
    const evaluatedDate = evaluation.evaluated_at
      ? new Date(evaluation.evaluated_at).toLocaleString('vi-VN')
      : new Date().toLocaleString('vi-VN');

    const categoryRows = Object.entries(evaluation.category_scores || {})
      .map(
        ([cat, score]) =>
          `<tr><td>${escapeHtml(cat.replace(/_/g, ' '))}</td><td style="text-align:right;font-weight:700">${score} / 10</td></tr>`
      )
      .join('');

    const questionsHtml = evaluation.responses
      .map((r) => {
        const candidateAns = r.is_skipped
          ? '<em>(Đã bỏ qua câu hỏi này)</em>'
          : escapeHtml(userAnswers?.[r.question_order] || '(Xem tại phần Bản ghi câu trả lời)');
        const strengthsHtml = (r.strengths || []).map((s) => `<li>${escapeHtml(s)}</li>`).join('');
        const missingHtml = (r.missing_points || []).map((m) => `<li>${escapeHtml(m)}</li>`).join('');
        return `
          <div class="q-block">
            <div class="q-header">
              <strong>Câu ${r.question_order}: ${escapeHtml(r.question_text)}</strong>
              <span class="q-score">${r.total_score} / 10 điểm</span>
            </div>
            <div class="q-meta">Nhóm: ${escapeHtml(r.category)} &nbsp;|&nbsp; Mức độ: ${escapeHtml(r.difficulty)}</div>
            <p><strong>Câu trả lời của ứng viên:</strong><br/>${candidateAns}</p>
            <p class="rubric">
              <strong>Điểm Rubric:</strong> Kỹ thuật: ${r.technical_accuracy}/4.0 | Đầy đủ: ${r.completeness}/2.0 | Lập luận: ${r.reasoning_clarity}/2.0 | Trọng tâm: ${r.relevance}/1.0 | Ví dụ: ${r.practical_example}/1.0
            </p>
            <p><strong>Nhận xét của AI:</strong> ${escapeHtml(r.feedback)}</p>
            ${strengthsHtml ? `<p><strong>Điểm tốt:</strong></p><ul>${strengthsHtml}</ul>` : ''}
            ${missingHtml ? `<p><strong>Điểm còn thiếu:</strong></p><ul>${missingHtml}</ul>` : ''}
            ${r.suggested_answer ? `<div class="suggested"><strong>Câu trả lời mẫu gợi ý:</strong><br/>${escapeHtml(r.suggested_answer)}</div>` : ''}
          </div>
        `;
      })
      .join('');

    const printWindow = window.open('', '_blank', 'width=960,height=800');
    if (!printWindow) {
      window.print();
      return;
    }

    printWindow.document.write(`<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="utf-8" />
  <title>Báo cáo Đánh giá Phỏng vấn ${attemptNumber ? `- Lần ${attemptNumber}` : ''}</title>
  <style>
    body { font-family: Arial, sans-serif; color: #0f172a; line-height: 1.55; margin: 28px; font-size: 13px; }
    h1 { color: #1d4ed8; font-size: 20px; margin-bottom: 4px; text-align: center; }
    .sub { text-align: center; color: #64748b; font-size: 12px; margin-bottom: 20px; }
    h2 { font-size: 15px; border-bottom: 2px solid #e2e8f0; padding-bottom: 4px; margin-top: 22px; color: #0f172a; }
    table { width: 100%; border-collapse: collapse; margin: 10px 0; }
    th, td { border: 1px solid #cbd5e1; padding: 8px 10px; text-align: left; }
    th { background: #f1f5f9; font-size: 12px; }
    .q-block { border: 1px solid #cbd5e1; border-radius: 8px; padding: 12px 14px; margin-bottom: 14px; page-break-inside: avoid; }
    .q-header { display: flex; justify-content: space-between; gap: 12px; font-size: 14px; }
    .q-score { color: #1d4ed8; font-weight: 700; white-space: nowrap; }
    .q-meta { font-size: 11px; color: #475569; margin: 4px 0 8px; }
    .rubric { background: #f8fafc; padding: 6px 8px; border-radius: 4px; font-size: 12px; }
    .suggested { background: #eff6ff; border-left: 3px solid #2563eb; padding: 8px 10px; margin-top: 8px; white-space: pre-wrap; }
    ul { margin: 4px 0 8px 18px; padding: 0; }
  </style>
</head>
<body>
  <h1>BÁO CÁO ĐÁNH GIÁ KẾT QUẢ PHỎNG VẤN</h1>
  <div class="sub">Vị trí: Backend Developer Intern ${attemptNumber ? `| Lần luyện số: ${attemptNumber}` : ''} | Ngày xuất: ${escapeHtml(evaluatedDate)}</div>

  <h2>1. Tổng quan kết quả</h2>
  <table>
    <tr><th>Tổng điểm</th><th>Điểm trung bình</th><th>Mức độ sẵn sàng</th><th>Đã trả lời / Bỏ qua</th></tr>
    <tr>
      <td><strong>${evaluation.total_score} / 100</strong></td>
      <td><strong>${evaluation.average_score} / 10</strong></td>
      <td><strong>${escapeHtml(badge.text)}</strong></td>
      <td>${evaluation.answered_count}/10 trả lời — ${evaluation.skipped_count}/10 bỏ qua</td>
    </tr>
  </table>

  ${categoryRows ? `<h2>2. Điểm trung bình theo nhóm chủ đề</h2><table><tr><th>Nhóm chủ đề</th><th style="text-align:right">Điểm trung bình</th></tr>${categoryRows}</table>` : ''}

  <h2>3. Nhận xét tổng thể &amp; Lộ trình cải thiện</h2>
  <p><strong>Nhận xét tổng quát:</strong> ${escapeHtml(evaluation.overall_summary || '')}</p>
  <p><strong>Điểm mạnh nổi bật:</strong></p>
  <ul>${(evaluation.key_strengths || []).map((s) => `<li>${escapeHtml(s)}</li>`).join('')}</ul>
  <p><strong>Lỗ hổng kiến thức cần lưu ý:</strong></p>
  <ul>${(evaluation.knowledge_gaps || []).map((g) => `<li>${escapeHtml(g)}</li>`).join('')}</ul>
  <p><strong>Kế hoạch học tập ngắn hạn:</strong></p>
  <ul>${(evaluation.short_term_study_plan || []).map((p) => `<li>${escapeHtml(p)}</li>`).join('')}</ul>
  ${evaluation.next_interview_advice ? `<p><strong>Lời khuyên cho buổi phỏng vấn tiếp theo:</strong> <em>${escapeHtml(evaluation.next_interview_advice)}</em></p>` : ''}

  <h2>4. Chi tiết đánh giá 10 câu hỏi</h2>
  ${questionsHtml}
</body>
</html>`);
    printWindow.document.close();
    printWindow.focus();
    setTimeout(() => {
      printWindow.print();
    }, 250);
  };

  if (loading) {
    return (
      <div className="mt-8 border-t border-slate-200 pt-8">
        <p className="animate-pulse text-sm text-slate-500">Đang kiểm tra báo cáo đánh giá...</p>
      </div>
    );
  }

  // View: Evaluation evaluated -> Render full report
  if (evaluation && evaluation.status === 'evaluated') {
    const badge = getReadinessBadge(evaluation.readiness_level);
    return (
      <section className="panel-reveal mt-8 space-y-8 border-t border-slate-200 pt-8" aria-labelledby="evaluation-report-title">
        <div className="flex flex-col justify-between gap-4 border-b border-slate-200 pb-6 md:flex-row md:items-end">
          <div>
            <p className="text-xs font-semibold tracking-[0.12em] text-blue-700 uppercase">05 · Kết quả buổi luyện</p>
            <h2 id="evaluation-report-title" className="mt-1 text-2xl font-bold tracking-tight text-slate-950">Báo cáo Đánh giá Buổi phỏng vấn</h2>
            <p className="mt-1 text-sm text-slate-500">Đánh giá tự động theo Rubric chuẩn Backend Developer Intern</p>
          </div>
          <div className="flex flex-wrap items-center gap-2.5">
            <span className={`rounded-md border px-3.5 py-2 text-sm font-semibold ${badge.className}`}>
              {badge.text}
            </span>
            {showCompletionLinks && (
              <div className="flex flex-wrap items-center gap-2">
                <Link
                  href="/result"
                  className="inline-flex items-center rounded-lg bg-blue-700 px-3.5 py-2 text-sm font-semibold text-white transition hover:bg-blue-800 focus-visible:ring-4 focus-visible:ring-blue-200"
                >
                  Xem kết quả đầy đủ
                </Link>
                <Link
                  href="/progress"
                  className="inline-flex items-center rounded-lg px-3 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-100 focus-visible:ring-4 focus-visible:ring-slate-100"
                >
                  Xem tiến bộ
                </Link>
              </div>
            )}
          </div>
        </div>

        <div className="flex flex-col gap-3 rounded-xl border border-slate-200 bg-slate-50/75 p-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm font-semibold text-slate-900">Lưu báo cáo</p>
            <p className="mt-0.5 text-xs leading-5 text-slate-600">Tải Word để tiếp tục chỉnh sửa, hoặc mở hộp in của trình duyệt để lưu PDF.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={handleDownloadDocx}
              disabled={exportingDocx}
              className="btn-primary-glow inline-flex items-center gap-1.5 rounded-lg bg-blue-700 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-800 focus-visible:ring-4 focus-visible:ring-blue-200 disabled:cursor-not-allowed disabled:bg-slate-300"
            >
              {exportingDocx && <span className="spinner-inline" aria-hidden="true" />}
              {exportingDocx ? 'Đang chuẩn bị Word...' : 'Tải Word (.docx)'}
            </button>
            <button
              type="button"
              onClick={handleExportPdf}
              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 focus-visible:ring-4 focus-visible:ring-slate-100"
            >
              In / lưu PDF
            </button>
          </div>
        </div>

        {exportNotice && (
          <p className="panel-reveal -mt-4 text-xs font-medium text-emerald-700" role="status">{exportNotice}</p>
        )}

        {error && (
          <div role="alert" className="rounded-lg border-l-4 border-red-500 bg-red-50 p-3 text-sm text-red-800">
            {error}
          </div>
        )}

        {/* Score Overview Cards */}
        <div className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-slate-200 bg-slate-200 sm:grid-cols-4">
          <div className="bg-blue-50 p-4">
            <span className="block text-xs font-medium text-blue-700">Tổng điểm</span>
            <span className="mt-1 block font-mono text-3xl font-extrabold text-blue-950 tabular-nums">
              {evaluation.total_score}
              <span className="text-sm font-normal text-blue-600">/100</span>
            </span>
          </div>

          <div className="bg-white p-4">
            <span className="block text-xs font-medium text-slate-500">Điểm trung bình</span>
            <span className="mt-1 block font-mono text-3xl font-extrabold text-slate-900 tabular-nums">
              {evaluation.average_score}
              <span className="text-sm font-normal text-slate-500">/10</span>
            </span>
          </div>

          <div className="bg-white p-4">
            <span className="block text-xs font-medium text-slate-500">Đã trả lời</span>
            <span className="mt-1 block font-mono text-3xl font-extrabold text-slate-900 tabular-nums">
              {evaluation.answered_count}
              <span className="text-sm font-normal text-slate-500">/10</span>
            </span>
          </div>

          <div className="bg-white p-4">
            <span className="block text-xs font-medium text-slate-500">Bỏ qua</span>
            <span className="mt-1 block font-mono text-3xl font-extrabold text-slate-900 tabular-nums">
              {evaluation.skipped_count}
              <span className="text-sm font-normal text-slate-500">/10</span>
            </span>
          </div>
        </div>

        {/* Category Breakdown */}
        {evaluation.category_scores && Object.keys(evaluation.category_scores).length > 0 && (
          <div className="rounded-xl bg-slate-50 p-5 sm:p-6">
            <h3 className="mb-4 text-base font-semibold text-slate-900">Điểm trung bình theo nhóm chủ đề</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
              {Object.entries(evaluation.category_scores).map(([cat, score]) => (
                <div key={cat} className="flex items-center justify-between rounded-lg bg-white p-3">
                  <span className="text-xs font-medium text-gray-700 capitalize">
                    {cat.replace(/_/g, ' ')}
                  </span>
                  <span className="font-mono text-sm font-bold text-slate-900 tabular-nums">{score}/10</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Overall Summary & Insights */}
        <div className="space-y-7 border-y border-slate-200 py-7">
          <div>
            <h3 className="text-base font-semibold text-gray-900 mb-2">Nhận xét tổng thể</h3>
            <p className="rounded-lg bg-slate-50 p-4 text-sm leading-7 text-slate-700">
              {evaluation.overall_summary}
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <h4 className="text-sm font-semibold text-green-800 mb-2 flex items-center">
                <span className="w-2 h-2 bg-green-500 rounded-full mr-2"></span>
                Điểm mạnh nổi bật
              </h4>
              <ul className="list-disc pl-5 space-y-1 text-sm text-gray-700">
                {(evaluation.key_strengths || []).map((str, idx) => (
                  <li key={idx}>{str}</li>
                ))}
              </ul>
            </div>

            <div>
              <h4 className="text-sm font-semibold text-amber-800 mb-2 flex items-center">
                <span className="w-2 h-2 bg-amber-500 rounded-full mr-2"></span>
                Lỗ hổng kiến thức cần lưu ý
              </h4>
              <ul className="list-disc pl-5 space-y-1 text-sm text-gray-700">
                {(evaluation.knowledge_gaps || []).map((gap, idx) => (
                  <li key={idx}>{gap}</li>
                ))}
              </ul>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-4 border-t border-gray-100">
            <div>
              <h4 className="mb-2 text-sm font-semibold text-blue-800">Ưu tiên cải thiện hàng đầu</h4>
              <ul className="list-disc pl-5 space-y-1 text-sm text-gray-700">
                {(evaluation.priority_improvements || []).map((item, idx) => (
                  <li key={idx}>{item}</li>
                ))}
              </ul>
            </div>

            <div>
              <h4 className="text-sm font-semibold text-blue-800 mb-2">Kế hoạch học tập ngắn hạn</h4>
              <ul className="list-disc pl-5 space-y-1 text-sm text-gray-700">
                {(evaluation.short_term_study_plan || []).map((plan, idx) => (
                  <li key={idx}>{plan}</li>
                ))}
              </ul>
            </div>
          </div>

          {evaluation.next_interview_advice && (
            <div className="pt-4 border-t border-gray-100">
              <h4 className="text-sm font-semibold text-gray-900 mb-2">Lời khuyên cho buổi phỏng vấn tiếp theo</h4>
              <p className="text-sm text-gray-600 italic bg-blue-50/50 p-3 rounded-lg border border-blue-100">
                &ldquo;{evaluation.next_interview_advice}&rdquo;
              </p>
            </div>
          )}
        </div>

        {/* Detailed 10 Questions Breakdown */}
        <div className="space-y-4">
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-lg font-bold text-gray-900">Chi tiết đánh giá từng câu hỏi (10 câu)</h3>
            <button
              type="button"
              onClick={() => setExpandAll((prev) => !prev)}
              className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50"
            >
              {expandAll ? 'Thu gọn tất cả ▲' : 'Mở rộng tất cả ▼'}
            </button>
          </div>
          {evaluation.responses.map((r, index) => {
            const isExpanded = expandAll || expandedIndex === index;
            const candidateAns = userAnswers?.[r.question_order];
            return (
              <div key={r.interview_response_id} className="overflow-hidden rounded-xl border border-slate-200 bg-white">
                <button
                  type="button"
                  onClick={() => {
                    if (expandAll) {
                      setExpandAll(false);
                      setExpandedIndex(index);
                    } else {
                      setExpandedIndex(isExpanded ? null : index);
                    }
                  }}
                  className="flex w-full items-start justify-between p-5 text-left hover:bg-slate-50 focus-visible:ring-4 focus-visible:ring-blue-100"
                >
                  <div className="pr-4">
                    <div className="flex items-center space-x-2 mb-1">
                      <span className="font-semibold text-gray-900 text-base">Câu {r.question_order}</span>
                      <span className="px-2 py-0.5 bg-blue-50 text-blue-700 text-xs font-medium rounded">
                        {r.category}
                      </span>
                      <span className="px-2 py-0.5 bg-gray-100 text-gray-600 text-xs font-medium rounded">
                        {r.difficulty}
                      </span>
                      {r.is_skipped && (
                        <span className="px-2 py-0.5 bg-amber-100 text-amber-800 text-xs font-medium rounded">
                          Đã bỏ qua
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-gray-800 font-medium">{r.question_text}</p>
                  </div>

                  <div className="text-right shrink-0">
                    <span className="font-mono text-lg font-bold text-blue-700 tabular-nums">{r.total_score}</span>
                    <span className="text-xs text-gray-500"> / 10 điểm</span>
                    <span className="mt-1 flex items-center justify-end gap-1 text-xs font-medium text-slate-500">
                      {isExpanded ? 'Thu gọn' : 'Chi tiết'}
                      <svg
                        className={`size-3.5 transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`}
                        viewBox="0 0 20 20"
                        fill="currentColor"
                        aria-hidden="true"
                      >
                        <path
                          fillRule="evenodd"
                          d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z"
                          clipRule="evenodd"
                        />
                      </svg>
                    </span>
                  </div>
                </button>

                {isExpanded && (
                  <div className="panel-reveal p-5 border-t border-gray-100 bg-gray-50/50 space-y-4">
                    {!r.is_skipped && candidateAns && (
                      <div>
                        <h5 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1">
                          Câu trả lời của bạn
                        </h5>
                        <div className="text-sm text-gray-800 bg-white p-3 rounded border border-gray-200 whitespace-pre-wrap">
                          {candidateAns}
                        </div>
                      </div>
                    )}
                    {/* Rubric Breakdown */}
                    <div>
                      <h5 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
                        Điểm theo tiêu chí Rubric
                      </h5>
                      <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
                        <div className="p-2 bg-white rounded border border-gray-200 text-center">
                          <span className="text-xs text-gray-500 block">Kỹ thuật</span>
                          <span className="text-sm font-bold text-gray-800">{r.technical_accuracy}/4.0</span>
                        </div>
                        <div className="p-2 bg-white rounded border border-gray-200 text-center">
                          <span className="text-xs text-gray-500 block">Đầy đủ</span>
                          <span className="text-sm font-bold text-gray-800">{r.completeness}/2.0</span>
                        </div>
                        <div className="p-2 bg-white rounded border border-gray-200 text-center">
                          <span className="text-xs text-gray-500 block">Lập luận</span>
                          <span className="text-sm font-bold text-gray-800">{r.reasoning_clarity}/2.0</span>
                        </div>
                        <div className="p-2 bg-white rounded border border-gray-200 text-center">
                          <span className="text-xs text-gray-500 block">Trọng tâm</span>
                          <span className="text-sm font-bold text-gray-800">{r.relevance}/1.0</span>
                        </div>
                        <div className="p-2 bg-white rounded border border-gray-200 text-center">
                          <span className="text-xs text-gray-500 block">Ví dụ thực tế</span>
                          <span className="text-sm font-bold text-gray-800">{r.practical_example}/1.0</span>
                        </div>
                      </div>
                    </div>

                    {/* Feedback */}
                    <div>
                      <h5 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1">
                        Nhận xét đánh giá
                      </h5>
                      <p className="text-sm text-gray-700 bg-white p-3 rounded border border-gray-200">
                        {r.feedback}
                      </p>
                    </div>

                    {/* Strengths & Missing Points */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      {r.strengths && r.strengths.length > 0 && (
                        <div>
                          <h6 className="text-xs font-semibold text-green-700 uppercase tracking-wider mb-1">
                            Điểm tốt
                          </h6>
                          <ul className="list-disc pl-5 space-y-1 text-xs text-gray-700">
                            {r.strengths.map((s, i) => (
                              <li key={i}>{s}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {r.missing_points && r.missing_points.length > 0 && (
                        <div>
                          <h6 className="text-xs font-semibold text-amber-700 uppercase tracking-wider mb-1">
                            Điểm còn thiếu
                          </h6>
                          <ul className="list-disc pl-5 space-y-1 text-xs text-gray-700">
                            {r.missing_points.map((m, i) => (
                              <li key={i}>{m}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>

                    {/* Suggested Answer */}
                    {r.suggested_answer && (
                      <div>
                        <h5 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1">
                          Câu trả lời gợi ý
                        </h5>
                        <div className="text-xs text-gray-700 bg-blue-50/50 p-3 rounded border border-blue-100 whitespace-pre-wrap">
                          {r.suggested_answer}
                        </div>
                      </div>
                    )}

                    {/* Study Topics */}
                    {r.study_topics && r.study_topics.length > 0 && (
                      <div>
                        <h5 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1">
                          Chủ đề nên ôn tập
                        </h5>
                        <div className="flex flex-wrap gap-1.5">
                          {r.study_topics.map((topic, i) => (
                            <span key={i} className="px-2 py-0.5 bg-gray-200 text-gray-700 text-xs rounded">
                              {topic}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </section>
    );
  }

  // View: Not evaluated yet or evaluation_failed -> Render Consent & Start Evaluation Button
  return (
    <section className="mt-8 border-t border-slate-200 pt-8" aria-labelledby="evaluation-start-title">
      <div className="rounded-xl bg-slate-50 p-5 sm:p-6">
        <p className="text-xs font-semibold tracking-[0.12em] text-blue-700 uppercase">Bước cuối của lần luyện</p>
        <h3 id="evaluation-start-title" className="mt-1 text-xl font-bold tracking-tight text-slate-950">Đánh giá buổi phỏng vấn bằng AI</h3>
        <p className="mt-2 text-sm leading-6 text-slate-600">
          AI sẽ chấm điểm chi tiết 10 câu trả lời theo rubric chuẩn dành cho Backend Developer Intern, đưa ra lời khuyên và lộ trình ôn luyện.
        </p>

        <label className="mt-5 flex cursor-pointer items-start gap-3 border-t border-slate-200 pt-5 group">
          <div className="flex items-center h-5">
            <input
              type="checkbox"
              checked={consent}
              onChange={(e) => setConsent(e.target.checked)}
              disabled={submitting}
              className="size-4 rounded border border-slate-300 bg-white text-blue-700 focus:ring-4 focus:ring-blue-200 disabled:opacity-50"
            />
          </div>
          <span className="text-sm text-gray-700 group-hover:text-gray-900">
            Tôi đồng ý gửi các câu trả lời phỏng vấn để AI thực hiện đánh giá và chấm điểm.
          </span>
        </label>

        {error && (
          <div role="alert" className="mt-4 rounded-lg border-l-4 border-red-500 bg-red-50 p-3 text-sm text-red-800">
            {error}
          </div>
        )}

        <button
          type="button"
          onClick={handleEvaluate}
          disabled={!consent || submitting}
          className="btn-primary-glow mt-5 inline-flex w-full items-center justify-center rounded-lg bg-blue-700 px-6 py-2.5 text-sm font-semibold text-white hover:bg-blue-800 focus-visible:ring-4 focus-visible:ring-blue-200 disabled:cursor-not-allowed disabled:bg-slate-300 sm:w-auto"
        >
          {submitting && <span className="spinner-inline mr-2" aria-hidden="true" />}
          {submitting
            ? 'Đang đánh giá buổi phỏng vấn...'
            : evaluation?.status === 'evaluation_failed'
            ? 'Thử lại đánh giá'
            : 'Đánh giá buổi phỏng vấn'}
        </button>
      </div>
    </section>
  );
}
