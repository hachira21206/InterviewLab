'use client';
import { useState, useEffect, useRef, useCallback } from 'react';
import {
  SessionStatus,
  InterviewHistoryItem,
  InterviewHistoryListResponse,
  isInterviewHistoryListResponse,
  isInterviewSessionResponse,
} from '../types/interview';

export type { SessionStatus, InterviewHistoryItem, InterviewHistoryListResponse };
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
}

export default function InterviewHistory({
  applicationId,
  selectedSessionId,
  onSelectSession,
  onAttemptCreated,
}: Props) {
  const [history, setHistory] = useState<InterviewHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [isCreatingAttempt, setIsCreatingAttempt] = useState(false);
  const [consent, setConsent] = useState(false);
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
          setSchemaError('Dữ liệu lịch sử không hợp lệ (không phải JSON).');
        }
        return false;
      }

      const data = (await res.json()) as unknown;
      if (!isMountedRef.current) return false;

      if (!res.ok) {
        setError('Không thể tải lịch sử phỏng vấn.');
        return false;
      }

      if (isInterviewHistoryListResponse(data)) {
        setHistory(data.items);
        setSchemaError(null);
        return true;
      } else {
        setSchemaError('Phản hồi lịch sử không đúng định dạng chuẩn.');
        return false;
      }
    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'AbortError') {
        return false;
      }
      if (isMountedRef.current) {
        setError(err instanceof Error ? err.message : 'Lỗi khi tải lịch sử.');
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

  const handleCreateAttempt = async () => {
    if (isCreatingAttempt || !consent || hasActiveAttempt) return;

    if (createAttemptAbortRef.current) {
      createAttemptAbortRef.current.abort();
    }
    const abortController = new AbortController();
    createAttemptAbortRef.current = abortController;

    setIsCreatingAttempt(true);
    setError(null);
    setSchemaError(null);

    try {
      const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://127.0.0.1:8000';
      const res = await fetch(
        `${backendUrl}/api/v1/job-applications/${applicationId}/interview-sessions/attempts`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ consent_to_external_ai: consent }),
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
    <section className="border-t border-slate-200 pt-8" aria-labelledby="interview-history-title">
      <div className="mb-5 flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold tracking-[0.12em] text-blue-700 uppercase">Các lần luyện</p>
          <h2 id="interview-history-title" className="mt-1 text-xl font-bold tracking-tight text-slate-950">Lịch sử luyện phỏng vấn</h2>
          <p className="mt-1 text-sm leading-6 text-slate-600">
            Xem lại các lần luyện trước hoặc bắt đầu một lần luyện mới độc lập.
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
      {history.length === 0 ? (
        <div className="mb-6 rounded-xl border border-dashed border-slate-300 bg-slate-50 p-7 text-center text-sm leading-6 text-slate-500">
          Chưa có lần luyện phỏng vấn nào. Bạn có thể bắt đầu lần luyện đầu tiên bên dưới.
        </div>
      ) : (
        <div className="mb-6 space-y-2">
          {history.map((item) => {
            const isSelected = selectedSessionId === item.id;
            const isEvaluated = item.total_score !== null;
            const isCompleted = item.status === 'completed';
            const isActive = ['ready', 'in_progress'].includes(item.status);

            return (
              <div
                key={item.id}
                className={`rounded-lg border-l-4 p-4 transition-colors ${
                  isSelected
                    ? 'border-blue-600 bg-blue-50/60'
                    : 'border-slate-200 bg-slate-50/60 hover:border-slate-400 hover:bg-white'
                }`}
              >
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-slate-900">
                        Lần luyện số {item.attempt_number}
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
                      className={`rounded-md px-3 py-1.5 text-xs font-medium ${
                        isSelected
                          ? 'bg-blue-700 text-white'
                          : 'bg-white text-blue-700 hover:bg-blue-50'
                      }`}
                    >
                      {isActive ? 'Tiếp tục luyện' : isEvaluated ? 'Xem báo cáo' : 'Xem câu hỏi'}
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Start New Attempt Section */}
      <div className="border-l-4 border-blue-600 bg-blue-50/70 p-5">
        <h3 className="mb-1 text-sm font-bold text-blue-950">
          Luyện phỏng vấn lần mới
        </h3>
        <p className="mb-3 text-xs leading-5 text-blue-800">
          {hasActiveAttempt
            ? 'Bạn đang có một lần luyện chưa hoàn tất. Vui lòng hoàn thành lần luyện hiện tại trước khi bắt đầu lần luyện mới.'
            : 'Bạn đã hoàn thành lượt luyện hiện tại. Bắt đầu một lượt luyện mới với 10 câu hỏi độc lập được sinh riêng.'}
        </p>

        {!hasActiveAttempt && (
          <div className="space-y-3">
            <label className="flex cursor-pointer items-start gap-2 text-xs leading-5 text-slate-700">
              <input
                type="checkbox"
                checked={consent}
                onChange={(e) => setConsent(e.target.checked)}
                className="mt-0.5 rounded border-slate-300 text-blue-700 focus:ring-blue-200"
              />
              <span>
                Tôi đồng ý gửi dữ liệu hồ sơ để AI sinh bộ câu hỏi mới cho lần luyện này.
              </span>
            </label>

            <button
              onClick={handleCreateAttempt}
              disabled={isCreatingAttempt || !consent}
              className="rounded-lg bg-blue-700 px-5 py-2.5 text-xs font-semibold text-white hover:bg-blue-800 focus-visible:ring-4 focus-visible:ring-blue-200 disabled:cursor-not-allowed disabled:bg-slate-300"
            >
              {isCreatingAttempt ? 'Đang tạo lần luyện mới...' : 'Luyện phỏng vấn lần mới'}
            </button>
          </div>
        )}
      </div>
    </section>
  );
}
