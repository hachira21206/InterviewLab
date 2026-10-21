'use client';
import Link from 'next/link';
import { useState, useEffect, useRef, useCallback } from 'react';
import {
  SessionStatus,
  PracticeMode,
  QuestionCategory,
  InterviewHistoryItem,
  InterviewHistoryListResponse,
  isInterviewHistoryListResponse,
  isInterviewSessionResponse,
} from '../types/interview';
import PracticeModeSelector from './PracticeModeSelector';

export type { SessionStatus, PracticeMode, QuestionCategory, InterviewHistoryItem, InterviewHistoryListResponse };
export { isInterviewHistoryItem, isInterviewHistoryListResponse, isInterviewSessionResponse } from '../types/interview';

function getStatusBadge(status: SessionStatus) {
  switch (status) {
    case 'generating':
      return <span className="rounded-md bg-amber-100 px-2.5 py-1 text-xs font-medium text-amber-900">Đang tạo câu hỏi</span>;
    case 'generation_failed':
      return <span className="rounded-md bg-red-100 px-2.5 py-1 text-xs font-medium text-red-900">Lỗi tạo câu hỏi</span>;
    case 'ready':
      return <span className="rounded-md bg-blue-100 px-2.5 py-1 text-xs font-medium text-blue-900">Sẵn sàng phỏng vấn</span>;
    case 'in_progress':
      return <span className="rounded-md bg-blue-700 px-2.5 py-1 text-xs font-medium text-white">Đang diễn ra</span>;
    case 'completed':
      return <span className="rounded-md bg-emerald-100 px-2.5 py-1 text-xs font-medium text-emerald-900">Đã hoàn thành</span>;
    default:
      return null;
  }
}

function getReadinessLabel(readiness: string | null) {
  switch (readiness) {
    case 'needs_foundation':
      return 'Cần củng cố nền tảng';
    case 'developing':
      return 'Đang phát triển';
    case 'intern_ready':
      return 'Sẵn sàng làm Intern';
    case 'strong_intern_candidate':
      return 'Ứng viên Intern xuất sắc';
    default:
      return readiness || 'Chưa đánh giá';
  }
}

interface Props {
  applicationId: string;
  selectedSessionId: string | null;
  onSelectSession: (sessionId: string) => void;
  onAttemptCreated: (sessionId: string) => void;
  viewMode?: 'practice' | 'results' | 'setup';
}

export default function InterviewHistory({
  applicationId,
  selectedSessionId,
  onSelectSession,
  onAttemptCreated,
  viewMode = 'practice',
}: Props) {
  const [history, setHistory] = useState<InterviewHistoryItem[]>([]);
  const [historyReady, setHistoryReady] = useState(false);
  const [loading, setLoading] = useState(true);
  const [isCreatingAttempt, setIsCreatingAttempt] = useState(false);
  const [consent, setConsent] = useState(false);
  const [practiceMode, setPracticeMode] = useState<PracticeMode>('full_mock');
  const [focusCategory, setFocusCategory] = useState<QuestionCategory>('database');
  const [error, setError] = useState<string | null>(null);
  const [schemaError, setSchemaError] = useState<string | null>(null);

  const isMountedRef = useRef(true);
  const historyAbortRef = useRef<AbortController | null>(null);
  const createAttemptAbortRef = useRef<AbortController | null>(null);

  const refreshHistory = useCallback(async (): Promise<boolean> => {
    if (historyAbortRef.current) {
      historyAbortRef.current.abort();
    }
    const abortController = new AbortController();
    historyAbortRef.current = abortController;

    try {
      const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://127.0.0.1:8000';
      const res = await fetch(`${backendUrl}/api/v1/job-applications/${applicationId}/interview-sessions`, {
        signal: abortController.signal,
      });

      const contentType = res.headers.get('content-type');
      if (!contentType || !contentType.includes('application/json')) {
        if (isMountedRef.current) {
          setHistoryReady(false);
          setSchemaError('Dữ liệu lịch sử không hợp lệ (không phải JSON).');
        }
        return false;
      }

      const data = (await res.json()) as unknown;
      if (!isMountedRef.current) return false;

      if (!res.ok) {
        setHistoryReady(false);
        setError('Không thể tải lịch sử phỏng vấn.');
        return false;
      }

      if (isInterviewHistoryListResponse(data, applicationId)) {
        setHistory(data.items);
        setHistoryReady(true);
        setSchemaError(null);
        setError(null);
        return true;
      } else {
        setHistory([]);
        setHistoryReady(false);
        setSchemaError('Phản hồi lịch sử không đúng định dạng chuẩn hoặc không khớp hồ sơ ứng tuyển.');
        return false;
      }
    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'AbortError') {
        return false;
      }
      if (isMountedRef.current) {
        setError(err instanceof Error ? err.message : 'Lỗi khi tải lịch sử.');
        setHistoryReady(false);
      }
      return false;
    } finally {
      if (isMountedRef.current) {
        setLoading(false);
      }
    }
  }, [applicationId]);

  useEffect(() => {
    isMountedRef.current = true;
    const prevAbort = historyAbortRef.current;

    // Use queueMicrotask / void to invoke refreshHistory cleanly asynchronously
    void Promise.resolve().then(() => {
      if (isMountedRef.current) {
        void refreshHistory();
      }
    });

    return () => {
      isMountedRef.current = false;
      prevAbort?.abort();
      historyAbortRef.current?.abort();
      createAttemptAbortRef.current?.abort();
    };
  }, [applicationId, refreshHistory]);

  const handleManualRefresh = async () => {
    if (loading) return;
    setLoading(true);
    setSchemaError(null);
    await refreshHistory();
  };

  const hasActiveAttempt = history.some((item) =>
    ['generating', 'generation_failed', 'ready', 'in_progress'].includes(item.status)
  );
  const visibleHistory = viewMode === 'results'
    ? history.filter((item) => item.status === 'completed')
    : history;

  const handleCreateAttempt = async () => {
    if (loading || !historyReady || isCreatingAttempt || !consent || hasActiveAttempt) return;

    if (createAttemptAbortRef.current) {
      createAttemptAbortRef.current.abort();
    }
    const abortController = new AbortController();
    createAttemptAbortRef.current = abortController;

    setIsCreatingAttempt(true);
    setError(null);
    setSchemaError(null);

    const requestPayload: {
      consent_to_external_ai: boolean;
      practice_mode: PracticeMode;
      focus_category?: QuestionCategory;
    } = {
      consent_to_external_ai: consent,
      practice_mode: practiceMode,
    };
    if (practiceMode === 'focus_category') {
      requestPayload.focus_category = focusCategory;
    }

    try {
      const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://127.0.0.1:8000';
      const res = await fetch(
        `${backendUrl}/api/v1/job-applications/${applicationId}/interview-sessions/attempts`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(requestPayload),
          signal: abortController.signal,
        }
      );

      const contentType = res.headers.get('content-type');
      if (!contentType || !contentType.includes('application/json')) {
        if (isMountedRef.current) {
          setSchemaError('Dữ liệu trả về không hợp lệ (không phải JSON).');
        }
        return;
      }

      const data = (await res.json()) as unknown;
      if (!isMountedRef.current) return;

      if (!res.ok) {
        if (res.status === 409) {
          const detail =
            data && typeof data === 'object' && 'detail' in data && typeof (data as { detail: unknown }).detail === 'string'
              ? (data as { detail: string }).detail
              : 'Đang có phiên phỏng vấn chưa hoàn thành.';
          setError(detail);
          await refreshHistory();
          return;
        }
        const detail =
          data && typeof data === 'object' && 'detail' in data && typeof (data as { detail: unknown }).detail === 'string'
              ? (data as { detail: string }).detail
              : 'Lỗi khi tạo lần luyện mới.';
        setError(detail);
        return;
      }

      if (!isInterviewSessionResponse(data, applicationId)) {
        setSchemaError('Phản hồi tạo phiên không đúng định dạng chuẩn.');
        return;
      }

      setConsent(false);
      const refreshed = await refreshHistory();
      if (isMountedRef.current && refreshed) {
        onAttemptCreated(data.id);
      }
    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'AbortError') {
        return;
      }
      if (isMountedRef.current) {
        setError(err instanceof Error ? err.message : 'Lỗi kết nối khi tạo lần luyện mới.');
      }
    } finally {
      if (isMountedRef.current) {
        setIsCreatingAttempt(false);
      }
    }
  };

  return (
    <section className={viewMode === 'setup' ? '' : 'border-t border-slate-200 pt-8'} aria-labelledby={viewMode === 'setup' ? 'new-attempt-title' : 'interview-history-title'}>
      {viewMode !== 'setup' && (
      <>
      <div className="mb-5 flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold tracking-[0.12em] text-blue-700 uppercase">{viewMode === 'results' ? 'Buổi đã hoàn thành' : 'Các lần luyện'}</p>
          <h2 id="interview-history-title" className="mt-1 text-xl font-bold tracking-tight text-slate-950">{viewMode === 'results' ? 'Chọn buổi để xem kết quả' : 'Lịch sử luyện phỏng vấn'}</h2>
          <p className="mt-1 text-sm leading-6 text-slate-600">
            {viewMode === 'results'
              ? 'Mỗi buổi có bản ghi câu trả lời và đánh giá riêng. Chọn buổi bạn muốn xem lại.'
              : 'Xem lại các lần luyện hoặc bắt đầu một buổi mới sau khi hoàn thành buổi hiện tại.'}
          </p>
        </div>
        <button
          onClick={handleManualRefresh}
          disabled={loading}
          className="shrink-0 rounded-md px-3 py-1.5 text-xs font-medium text-blue-700 hover:bg-blue-50 focus-visible:ring-4 focus-visible:ring-blue-100 disabled:opacity-50"
        >
          {loading ? 'Đang tải...' : 'Làm mới'}
        </button>
      </div>

      {schemaError && (
        <div role="alert" className="mb-4 rounded-lg border-l-4 border-red-500 bg-red-50 p-3 text-sm text-red-800">
          {schemaError}
        </div>
      )}

      {error && (
        <div role="alert" className="mb-4 rounded-lg border-l-4 border-red-500 bg-red-50 p-3 text-sm text-red-800">
          {error}
        </div>
      )}

      {/* Attempts List */}
      {visibleHistory.length === 0 ? (
        <div className="mb-6 rounded-xl border border-dashed border-slate-300 bg-slate-50 p-7 text-center text-sm leading-6 text-slate-500">
          {viewMode === 'results'
            ? loading ? 'Đang tải các buổi đã hoàn thành...' : 'Chưa có buổi phỏng vấn hoàn thành. Hãy hoàn thành một buổi để xem kết quả tại đây.'
            : 'Chưa có lần luyện nào. Bạn có thể bắt đầu lần luyện đầu tiên bên dưới.'}
        </div>
      ) : (
        <div className="mb-6 space-y-2">
          {visibleHistory.map((item) => {
            const isSelected = selectedSessionId === item.id;
            const isEvaluated = item.total_score !== null;
            const isCompleted = item.status === 'completed';
            const isActive = ['ready', 'in_progress'].includes(item.status);

            return (
              <div
                key={item.id}
                className={`rounded-xl border p-4 transition-all duration-150 ${
                  isSelected
                    ? 'border-blue-500 bg-blue-50/70 shadow-xs ring-2 ring-blue-500/20'
                    : 'border-slate-200/90 bg-white hover:border-slate-300 hover:bg-slate-50/60'
                }`}
              >
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-slate-900">
                        {item.mode_display_title || `Lần ${item.attempt_number} · Phỏng vấn tổng hợp`}
                      </span>
                      {getStatusBadge(item.status)}
                    </div>

                    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 font-mono text-xs text-slate-500 tabular-nums">
                      <span>
                        Ngày tạo: {new Date(item.created_at).toLocaleString('vi-VN', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit', year: 'numeric' })}
                      </span>
                      {isCompleted && (
                        <span>
                          Đã trả lời: {item.answered_count} | Bỏ qua: {item.skipped_count}
                        </span>
                      )}
                    </div>

                    {isEvaluated && (
                      <div className="flex items-center gap-2 pt-1 text-xs text-slate-700">
                        <span className="font-medium text-emerald-700">
                          Điểm số: {item.total_score} / 100
                        </span>
                        {item.average_score !== null && (
                          <span className="text-gray-500">
                            (TB: {item.average_score.toFixed(1)})
                          </span>
                        )}
                        <span className="text-gray-400">•</span>
                        <span className="px-2 py-0.5 rounded bg-emerald-50 text-emerald-800 font-medium">
                          {getReadinessLabel(item.readiness_level)}
                        </span>
                      </div>
                    )}
                  </div>

                  <div className="flex items-center gap-2 self-end sm:self-center">
                    <button
                      onClick={() => onSelectSession(item.id)}
                      className={`rounded-lg px-3.5 py-1.5 text-xs font-semibold shadow-2xs transition-colors ${
                        isSelected
                          ? 'bg-blue-700 text-white hover:bg-blue-800'
                          : 'border border-slate-200 bg-white text-blue-700 hover:bg-blue-50'
                      }`}
                    >
                      {viewMode === 'results'
                        ? 'Xem bài đã nộp'
                        : isActive ? 'Tiếp tục luyện' : 'Xem tóm tắt'}
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
      </>
      )}

      {/* Start New Attempt Section */}
      {(viewMode === 'practice' || viewMode === 'setup') && <div className="rounded-2xl border border-slate-200/90 bg-white p-6 shadow-xs sm:p-8">
        <div className="flex items-center gap-3">
          <div className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-blue-600 text-white shadow-xs shadow-blue-500/20">
            <span className="text-xl">🚀</span>
          </div>
          <div>
            <p className="text-[11px] font-bold tracking-[0.14em] text-blue-700 uppercase">Lần luyện tiếp theo</p>
            <h3 id="new-attempt-title" className="text-xl font-bold tracking-tight text-slate-950">Tạo bài luyện phỏng vấn</h3>
          </div>
        </div>

        <p className="mt-3 text-sm leading-6 text-slate-600">
          {hasActiveAttempt
            ? 'Bạn đang có một lần luyện chưa hoàn tất. Vui lòng hoàn thành lần luyện hiện tại trước khi bắt đầu lần luyện mới.'
            : history.length === 0
            ? 'Chọn một chế độ để tạo bộ 10 câu hỏi đầu tiên cho hồ sơ này.'
            : 'Bắt đầu một lượt luyện mới với 10 câu hỏi độc lập được sinh riêng.'}
        </p>

        {viewMode === 'setup' && schemaError && <div role="alert" className="mt-4 rounded-lg border-l-4 border-red-500 bg-red-50 p-3 text-sm text-red-800">{schemaError}</div>}
        {viewMode === 'setup' && error && <div role="alert" className="mt-4 rounded-lg border-l-4 border-red-500 bg-red-50 p-3 text-sm text-red-800">{error}</div>}

        {loading ? (
          <p className="mt-5 rounded-xl bg-slate-50 p-4 text-sm text-slate-600" role="status">Đang kiểm tra lượt luyện hiện tại...</p>
        ) : !historyReady ? (
          <div className="mt-5 rounded-xl bg-slate-50 p-4 text-sm text-slate-700">
            <p>Chưa kiểm tra được lượt luyện hiện tại. Hãy tải lại trước khi tạo bài mới.</p>
            <button type="button" onClick={handleManualRefresh} className="mt-3 rounded-lg bg-blue-700 px-4 py-2.5 font-semibold text-white hover:bg-blue-800 focus-visible:ring-4 focus-visible:ring-blue-200">Thử tải lại</button>
          </div>
        ) : hasActiveAttempt ? (
          <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50/80 p-4 text-sm text-amber-900">
            <p>Bạn đang có một lượt luyện chưa hoàn tất. Hãy tiếp tục lượt đó trước khi tạo bài mới.</p>
            <Link href="/interview" className="mt-3 inline-flex rounded-lg bg-blue-700 px-4 py-2.5 font-semibold text-white hover:bg-blue-800 focus-visible:ring-4 focus-visible:ring-blue-200">
              Tiếp tục buổi luyện
            </Link>
          </div>
        ) : (
          <div className="mt-6 border-t border-slate-100 pt-6 space-y-6">
            <PracticeModeSelector
              applicationId={applicationId}
              practiceMode={practiceMode}
              onPracticeModeChange={setPracticeMode}
              focusCategory={focusCategory}
              onFocusCategoryChange={setFocusCategory}
              disabled={isCreatingAttempt}
            />

            <label className="flex cursor-pointer select-none items-start gap-3 rounded-xl border border-slate-200/80 bg-slate-50/60 p-3.5 transition-colors hover:border-slate-300 hover:bg-slate-50 group">
              <div className="flex h-5 items-center">
                <input
                  type="checkbox"
                  checked={consent}
                  onChange={(e) => setConsent(e.target.checked)}
                  disabled={isCreatingAttempt}
                  className="size-4 rounded border border-slate-300 bg-white text-blue-700 focus:ring-4 focus:ring-blue-200 disabled:opacity-50"
                />
              </div>
              <span className="text-xs sm:text-sm leading-5 sm:leading-6 text-slate-700 group-hover:text-slate-950 font-medium">
                Tôi đồng ý gửi dữ liệu hồ sơ để AI sinh bộ câu hỏi mới cho lần luyện này.
              </span>
            </label>

            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pt-1">
              <button
                onClick={handleCreateAttempt}
                disabled={loading || !historyReady || isCreatingAttempt || !consent}
                className="btn-primary-glow inline-flex w-full items-center justify-center gap-2 rounded-xl bg-blue-700 px-7 py-3 text-sm font-bold text-white shadow-sm transition-all hover:bg-blue-800 focus-visible:ring-4 focus-visible:ring-blue-200 disabled:cursor-not-allowed disabled:bg-slate-300 sm:w-auto"
              >
                {isCreatingAttempt ? (
                  <span className="spinner-inline" aria-hidden="true" />
                ) : (
                  <span className="text-base" aria-hidden="true">🚀</span>
                )}
                {isCreatingAttempt ? 'Đang tạo bộ câu hỏi...' : 'Tạo bộ câu hỏi'}
              </button>
              <span className="text-[11px] text-slate-400 text-center sm:text-right font-medium">
                10 câu hỏi độc lập · Thời gian tạo ~5-15s
              </span>
            </div>
          </div>
        )}
      </div>}
    </section>
  );
}
