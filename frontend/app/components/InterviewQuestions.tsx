'use client';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useState, useEffect, useRef } from 'react';
import InterviewEvaluation from './InterviewEvaluation';
import QuestionVoiceTimerBar from './QuestionVoiceTimerBar';
import QuestionCoachHint from './QuestionCoachHint';
import {
  SessionStatus,
  PracticeMode,
  QuestionCategory,
  QuestionDifficulty,
  InterviewSessionResponse,
  isInterviewHistoryListResponse,
  isInterviewSessionResponse,
} from '../types/interview';

interface InterviewQuestionSummary {
  id: string;
  order_index: number;
  question_text: string;
  category: QuestionCategory;
  difficulty: QuestionDifficulty;
}

interface InterviewResponseDetail {
  id: string;
  interview_question_id: string;
  order_index: number;
  question_text: string;
  category: QuestionCategory;
  difficulty: QuestionDifficulty;
  answer_text: string | null;
  is_skipped: boolean;
  answered_at: string | null;
}

interface InterviewProgressResponse {
  session_id: string;
  status: SessionStatus;
  started_at: string | null;
  completed_at: string | null;
  total_questions: number;
  completed_count: number;
  progress_percent: number;
  current_question: InterviewQuestionSummary | null;
  responses: InterviewResponseDetail[];
}

function isApiError(value: unknown): value is { detail: string } {
  if (!value || typeof value !== 'object') return false;
  return typeof (value as Record<string, unknown>).detail === 'string';
}

function isInterviewQuestionSummary(data: unknown): data is InterviewQuestionSummary {
  if (!data || typeof data !== 'object') return false;
  const d = data as Record<string, unknown>;
  if (typeof d.id !== 'string') return false;
  if (typeof d.order_index !== 'number' || !Number.isInteger(d.order_index) || d.order_index < 1 || d.order_index > 10) return false;
  if (typeof d.question_text !== 'string') return false;
  const validCategories = ['backend_fundamentals', 'cv_project_experience', 'database', 'api_web_design', 'debugging_problem_solving', 'behavioral_teamwork'];
  if (typeof d.category !== 'string' || !validCategories.includes(d.category)) return false;
  const validDiffs = ['easy', 'medium', 'hard'];
  if (typeof d.difficulty !== 'string' || !validDiffs.includes(d.difficulty)) return false;
  return true;
}

function isInterviewResponseDetail(data: unknown): data is InterviewResponseDetail {
  if (!data || typeof data !== 'object') return false;
  const d = data as Record<string, unknown>;
  if (typeof d.id !== 'string' || typeof d.interview_question_id !== 'string') return false;
  if (typeof d.order_index !== 'number' || !Number.isInteger(d.order_index)) return false;
  if (typeof d.question_text !== 'string') return false;
  if (typeof d.is_skipped !== 'boolean') return false;
  if (d.answer_text !== null && typeof d.answer_text !== 'string') return false;
  return true;
}

function isInterviewProgressResponse(data: unknown): data is InterviewProgressResponse {
  if (!data || typeof data !== 'object') return false;
  const d = data as Record<string, unknown>;
  if (typeof d.session_id !== 'string') return false;
  if (typeof d.status !== 'string' || !['generating', 'ready', 'generation_failed', 'in_progress', 'completed'].includes(d.status)) return false;
  if (typeof d.total_questions !== 'number') return false;
  if (typeof d.completed_count !== 'number') return false;
  if (typeof d.progress_percent !== 'number') return false;
  if (d.current_question !== null && !isInterviewQuestionSummary(d.current_question)) return false;
  if (!Array.isArray(d.responses) || !d.responses.every(isInterviewResponseDetail)) return false;
  return true;
}

interface Props {
  applicationId: string;
  analysisCompleted: boolean;
  mode?: 'interview' | 'result' | 'report';
  selectedSessionId?: string | null;
}

export default function InterviewQuestions({ applicationId, analysisCompleted, mode = 'interview', selectedSessionId = null }: Props) {
  const router = useRouter();
  const [session, setSession] = useState<InterviewSessionResponse | null>(null);
  const [progress, setProgress] = useState<InterviewProgressResponse | null>(null);
  const [initialLoading, setInitialLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [consent, setConsent] = useState(false);
  const [finalAction, setFinalAction] = useState<'answer' | 'skip' | null>(null);
  const [answerText, setAnswerText] = useState('');
  const abortControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!analysisCompleted) return;
    
    const abortController = new AbortController();
    
    const fetchSessionAndProgress = async () => {
      try {
        const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://127.0.0.1:8000';
        let targetSessionId = selectedSessionId;
        if (!targetSessionId && mode !== 'interview') {
          const historyRes = await fetch(`${backendUrl}/api/v1/job-applications/${applicationId}/interview-sessions`, {
            signal: abortController.signal,
          });
          if (!historyRes.ok || !historyRes.headers.get('content-type')?.includes('application/json')) {
            throw new Error('Không thể tải danh sách bài đã nộp.');
          }
          const historyData = await historyRes.json() as unknown;
          if (!isInterviewHistoryListResponse(historyData, applicationId)) {
            throw new Error('Dữ liệu lịch sử không hợp lệ.');
          }
          targetSessionId = historyData.items.find((item) => item.status === 'completed')?.id ?? null;
          if (!targetSessionId) return;
        }
        const sessionPath = targetSessionId
          ? `${backendUrl}/api/v1/job-applications/${applicationId}/interview-sessions/${targetSessionId}`
          : `${backendUrl}/api/v1/job-applications/${applicationId}/interview-sessions/current`;
        const res = await fetch(sessionPath, {
          signal: abortController.signal
        });
        
        if (res.status === 404) return;
        
        const contentType = res.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
           throw new Error('Dữ liệu trả về không hợp lệ.');
        }
        
        const data = await res.json() as unknown;
        if (res.ok) {
          if (isInterviewSessionResponse(data, applicationId)) {
            setSession(data);
            if (data.status === 'generation_failed') {
               setError(data.error_message || 'Tạo câu hỏi thất bại.');
            } else if (data.status === 'in_progress' || data.status === 'completed') {
              // Fetch latest progress
              const progRes = await fetch(`${backendUrl}/api/v1/interview-sessions/${data.id}/progress`, {
                signal: abortController.signal
              });
              if (!progRes.ok || !progRes.headers.get('content-type')?.includes('application/json')) {
                throw new Error('Không thể tải tiến độ buổi luyện.');
              }
              const progData = await progRes.json() as unknown;
              if (!isInterviewProgressResponse(progData) || progData.session_id !== data.id) {
                throw new Error('Dữ liệu tiến độ không hợp lệ.');
              }
              setProgress(progData);
            }
          } else {
            throw new Error('Dữ liệu buổi luyện không hợp lệ.');
          }
        } else {
          throw new Error('Không thể tải buổi luyện.');
        }
      } catch (err: unknown) {
        if (!abortController.signal.aborted) {
          setLoadError(err instanceof Error ? err.message : 'Không thể tải buổi luyện.');
        }
      } finally {
        if (!abortController.signal.aborted) setInitialLoading(false);
      }
    };
    fetchSessionAndProgress();
    return () => abortController.abort();
  }, [applicationId, analysisCompleted, mode, selectedSessionId]);

  useEffect(() => {
    return () => {
      if (abortControllerRef.current) abortControllerRef.current.abort();
    };
  }, []);

  const handleRetryGeneration = async () => {
    if (loading || session?.status === 'generating') return;
    setLoading(true);
    setError(null);
    
    if (abortControllerRef.current) abortControllerRef.current.abort();
    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    const requestPayload: { consent_to_external_ai: boolean; practice_mode: PracticeMode } = {
      consent_to_external_ai: consent,
      practice_mode: 'full_mock',
    };
    
    try {
      const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://127.0.0.1:8000';
      const res = await fetch(`${backendUrl}/api/v1/job-applications/${applicationId}/interview-sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestPayload),
        signal: abortController.signal
      });
      
      const contentType = res.headers.get('content-type');
      if (!contentType || !contentType.includes('application/json')) {
         throw new Error('Dữ liệu trả về không hợp lệ.');
      }
      
      const data = await res.json() as unknown;
      
      if (!res.ok) {
        if (isApiError(data)) {
            setError(data.detail);
        } else {
            setError('Lỗi hệ thống.');
        }
      } else {
        if (isInterviewSessionResponse(data, applicationId)) {
          setSession(data);
          if (data.status === 'generation_failed') {
            setError(data.error_message || data.error_code || 'Tạo thất bại.');
          }
        } else {
          setError('Dữ liệu trả về không hợp lệ.');
        }
      }
    } catch (err: unknown) {
      if (err instanceof Error && err.name !== 'AbortError') {
        setError(err.message || 'Lỗi kết nối.');
      }
    } finally {
      if (!abortController.signal.aborted) {
         setLoading(false);
      }
    }
  };

  const handleStartInterview = async () => {
    if (!session || loading) return;
    setLoading(true);
    setError(null);

    if (abortControllerRef.current) abortControllerRef.current.abort();
    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    try {
      const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://127.0.0.1:8000';
      const res = await fetch(`${backendUrl}/api/v1/interview-sessions/${session.id}/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        signal: abortController.signal
      });

      const contentType = res.headers.get('content-type');
      if (!contentType || !contentType.includes('application/json')) {
         throw new Error('Dữ liệu trả về không hợp lệ.');
      }

      const data = await res.json() as unknown;
      if (!res.ok) {
        if (isApiError(data)) {
          setError(data.detail);
        } else {
          setError('Lỗi hệ thống khi bắt đầu phỏng vấn.');
        }
      } else {
        if (isInterviewProgressResponse(data)) {
          setProgress(data);
        } else {
          setError('Dữ liệu trả về không hợp lệ.');
        }
      }
    } catch (err: unknown) {
      if (err instanceof Error && err.name !== 'AbortError') {
        setError(err.message || 'Lỗi kết nối.');
      }
    } finally {
      if (!abortController.signal.aborted) {
        setLoading(false);
      }
    }
  };

  const handleSubmitResponse = async (isSkipped: boolean) => {
    if (submitting || !progress || !progress.current_question) return;

    if (!isSkipped && answerText.trim().length === 0) {
      setError('Vui lòng nhập câu trả lời trước khi gửi.');
      return;
    }

    setSubmitting(true);
    setError(null);

    if (abortControllerRef.current) abortControllerRef.current.abort();
    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    const payload = isSkipped
      ? { answer_text: null, is_skipped: true }
      : { answer_text: answerText, is_skipped: false };

    try {
      const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://127.0.0.1:8000';
      const res = await fetch(
        `${backendUrl}/api/v1/interview-sessions/${progress.session_id}/questions/${progress.current_question.id}/response`,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
          signal: abortController.signal
        }
      );

      const contentType = res.headers.get('content-type');
      if (!contentType || !contentType.includes('application/json')) {
        throw new Error('Dữ liệu trả về không hợp lệ.');
      }

      const data = await res.json() as unknown;
      if (!res.ok) {
        if (isApiError(data)) {
          setError(data.detail);
        } else {
          setError('Lỗi khi gửi câu trả lời.');
        }
      } else {
        if (isInterviewProgressResponse(data)) {
          setProgress(data);
          setAnswerText('');
          setFinalAction(null);
          if (data.status === 'completed') {
            router.push(`/result?sessionId=${data.session_id}`);
          }
        } else {
          setError('Dữ liệu trả về không hợp lệ.');
        }
      }
    } catch (err: unknown) {
      if (err instanceof Error && err.name !== 'AbortError') {
        setError(err.message || 'Lỗi kết nối mạng.');
      }
    } finally {
      if (!abortController.signal.aborted) {
        setSubmitting(false);
      }
    }
  };

  if (!analysisCompleted) return null;

  if (initialLoading) {
    return <div className="rounded-xl bg-slate-50 p-6 text-sm text-slate-600" role="status">Đang tải buổi luyện...</div>;
  }

  if (loadError) {
    return <div role="alert" className="rounded-xl border-l-4 border-red-500 bg-red-50 p-5 text-sm text-red-800">{loadError}</div>;
  }

  const isFinalQuestion = progress?.status === 'in_progress' &&
    progress.completed_count === progress.total_questions - 1;

  return (
    <section className="space-y-8" aria-labelledby="interview-workspace-title">
      <div>
        <p className="text-xs font-semibold tracking-[0.12em] text-blue-700 uppercase">{mode === 'report' ? 'Báo cáo đánh giá' : mode === 'result' ? 'Bài đã nộp' : 'Buổi luyện hiện tại'}</p>
        <h2 id="interview-workspace-title" className="mt-1 text-2xl font-bold tracking-tight text-slate-950">{mode === 'report' ? 'Nhận xét và điểm số' : mode === 'result' ? 'Câu trả lời của bạn' : 'Làm bài phỏng vấn'}</h2>
        <p className="mt-2 text-sm leading-6 text-slate-600">
          {mode === 'report'
            ? 'Báo cáo AI là bước riêng sau khi bạn đã xem lại bài làm.'
            : mode === 'result'
            ? 'Xem lại 10 câu đã trả lời hoặc bỏ qua, sau đó chuyển sang báo cáo đánh giá.'
            : 'Trả lời từng câu theo thứ tự. Ở câu cuối, xác nhận nộp bài để chuyển sang Kết quả.'}
        </p>
      </div>

      {/* 3. Active Session Details / Answering Interface / Transcript */}
      {progress?.status === 'completed' ? (
        <div className="border-t border-slate-200 pt-8">
          {mode === 'interview' ? (
            <>
              <div className="rounded-2xl border border-emerald-200 bg-emerald-50/70 p-6 sm:p-8">
                <p className="text-xs font-bold tracking-[0.12em] text-emerald-800 uppercase">Đã xong 10/10 câu</p>
                <h3 className="mt-2 text-2xl font-bold tracking-tight text-slate-950">Buổi luyện đã hoàn thành</h3>
                <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-700">
                  Câu trả lời của bạn đã được lưu. Sang Kết quả để xem lại từng câu và yêu cầu AI đánh giá khi bạn sẵn sàng.
                </p>
                <Link href={`/result?sessionId=${progress.session_id}`} className="mt-6 inline-flex rounded-xl bg-blue-700 px-5 py-3 text-sm font-semibold text-white transition hover:bg-blue-800">
                  Xem kết quả buổi luyện →
                </Link>
              </div>
            </>
          ) : (
          <>
          {mode === 'result' ? (
          <>
          <div className="mb-7 rounded-2xl border border-emerald-200/90 bg-gradient-to-r from-emerald-50/90 via-emerald-50/40 to-white p-6 shadow-xs sm:p-7">
            <div className="flex items-center gap-3.5">
              <div className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-emerald-600 text-white shadow-xs shadow-emerald-500/20 text-xl">
                🎉
              </div>
              <div>
                <p className="text-[11px] font-bold tracking-[0.14em] text-emerald-700 uppercase">Phiên luyện đã hoàn tất</p>
                <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-emerald-950">
                  Hoàn thành buổi phỏng vấn {session ? `(Lần luyện số ${session.attempt_number})` : ''}
                </h2>
              </div>
            </div>
            <p className="mt-2.5 text-sm leading-6 text-emerald-900">
              Bạn đã hoàn thành toàn bộ {progress.total_questions} câu hỏi phỏng vấn.
            </p>
            <Link href={`/report?sessionId=${progress.session_id}`} className="mt-5 inline-flex rounded-lg bg-blue-700 px-5 py-2.5 text-sm font-semibold text-white hover:bg-blue-800 focus-visible:ring-4 focus-visible:ring-blue-200">Xem báo cáo đánh giá →</Link>
          </div>

          <h3 className="mb-4 text-xl font-semibold text-slate-950">Bản ghi câu trả lời (Transcript)</h3>
          <div className="space-y-4">
            {progress.responses.map((r) => (
              <article key={r.id} className="rounded-xl border border-slate-200 bg-white p-5">
                <div className="mb-2 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <h4 className="text-base font-semibold leading-6 text-slate-900 sm:text-lg">
                    Câu {r.order_index}: {r.question_text}
                  </h4>
                  <div className="flex shrink-0 gap-2 sm:ml-4">
                    <span className="rounded-md bg-blue-50 px-2 py-1 text-xs font-medium text-blue-700">
                      {r.category}
                    </span>
                    <span
                      className={`rounded-md px-2 py-1 text-xs font-medium ${
                        r.difficulty === 'easy'
                          ? 'bg-green-50 text-green-700'
                          : r.difficulty === 'medium'
                          ? 'bg-yellow-50 text-yellow-700'
                          : 'bg-red-50 text-red-700'
                      }`}
                    >
                      {r.difficulty}
                    </span>
                  </div>
                </div>

                {r.is_skipped ? (
                  <div className="mt-3 rounded-lg bg-slate-100 p-3 text-sm text-slate-600 italic">
                    Đã bỏ qua câu hỏi này.
                  </div>
                ) : (
                  <div className="mt-3">
                    <span className="mb-1 block text-xs font-semibold tracking-wider text-slate-500 uppercase">
                      Câu trả lời của bạn:
                    </span>
                    <div className="rounded-lg bg-slate-50 p-4 text-sm leading-6 text-slate-800 whitespace-pre-wrap">
                      {r.answer_text}
                    </div>
                  </div>
                )}
              </article>
            ))}
          </div>
          </>
          ) : (
            <>
              <InterviewEvaluation
                sessionId={progress.session_id}
                attemptNumber={session?.attempt_number}
                showCompletionLinks
                userAnswers={Object.fromEntries(
                  progress.responses.map((r) => [r.order_index, r.answer_text])
                )}
              />
            </>
          )}
          </>
          )}
        </div>
      ) : mode === 'result' || mode === 'report' ? (
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-6 text-center">
          <p className="text-sm font-semibold text-slate-900">Chưa có bài đã nộp để xem</p>
          <p className="mt-2 text-sm leading-6 text-slate-600">Hoàn thành một buổi luyện trước, hoặc chọn bài cũ trong trang Tiến bộ.</p>
          <Link href="/interview" className="mt-5 inline-flex rounded-lg bg-blue-700 px-5 py-2.5 text-sm font-semibold text-white hover:bg-blue-800">Đi tới buổi luyện</Link>
        </div>
      ) : progress?.status === 'in_progress' && progress.current_question ? (
        <div className="border-t border-slate-200 pt-8">
          <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="text-xs font-semibold tracking-[0.12em] text-blue-700 uppercase">Đang thực hiện</p>
              <h2 className="mt-1 text-xl font-semibold text-slate-950">
              Buổi phỏng vấn trực tuyến {session ? `(Lần luyện số ${session.attempt_number})` : ''}
              </h2>
            </div>
            <span className="font-mono text-sm font-medium text-slate-500 tabular-nums">
              Tiến độ: {progress.completed_count}/{progress.total_questions} câu ({progress.progress_percent}%)
            </span>
          </div>

          <div className="mb-4 h-2 w-full overflow-hidden rounded-full bg-slate-200" role="progressbar" aria-valuenow={progress.progress_percent} aria-valuemin={0} aria-valuemax={100}>
            <div
              className="h-2 rounded-full bg-gradient-to-r from-blue-700 to-sky-500 transition-all duration-500 ease-out"
              style={{ width: `${progress.progress_percent}%` }}
            ></div>
          </div>

          <div className="mb-6 grid grid-cols-10 gap-1.5" aria-label="Chỉ báo trạng thái 10 câu hỏi">
            {Array.from({ length: progress.total_questions || 10 }, (_, idx) => {
              const order = idx + 1;
              const resp = progress.responses.find((r) => r.order_index === order);
              const isCurrent = progress.current_question?.order_index === order;
              const pillStyle = isCurrent
                ? 'border-blue-600 bg-blue-700 text-white shadow-sm ring-2 ring-blue-200'
                : resp?.is_skipped
                ? 'border-amber-300 bg-amber-50 text-amber-800'
                : resp
                ? 'border-emerald-300 bg-emerald-50 text-emerald-800'
                : 'border-slate-200 bg-white text-slate-400';
              return (
                <div
                  key={order}
                  title={
                    isCurrent
                      ? `Câu ${order}: Đang trả lời`
                      : resp?.is_skipped
                      ? `Câu ${order}: Đã bỏ qua`
                      : resp
                      ? `Câu ${order}: Đã trả lời`
                      : `Câu ${order}: Chưa đến`
                  }
                  className={`flex h-7 items-center justify-center rounded-md border font-mono text-xs font-bold transition-all duration-200 ${pillStyle}`}
                >
                  {order}
                </div>
              );
            })}
          </div>

          <article
            key={progress.current_question.id}
            className="card-transition rounded-2xl border border-blue-200 bg-white p-5 shadow-[0_20px_55px_-40px_rgba(29,78,216,0.7)] sm:p-7"
          >
            <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <span className="w-fit rounded-md bg-blue-700 px-3 py-1 text-sm font-semibold text-white">
                Câu {progress.current_question.order_index}/10
              </span>
              <div className="flex gap-2">
                <span className="rounded-md bg-blue-50 px-2.5 py-1 text-xs font-medium text-blue-700">
                  {progress.current_question.category}
                </span>
                <span
                  className={`rounded-md px-2.5 py-1 text-xs font-medium ${
                    progress.current_question.difficulty === 'easy'
                      ? 'bg-green-50 text-green-700'
                      : progress.current_question.difficulty === 'medium'
                      ? 'bg-yellow-50 text-yellow-700'
                      : 'bg-red-50 text-red-700'
                  }`}
                >
                  {progress.current_question.difficulty}
                </span>
              </div>
            </div>

            <h3 className="mb-7 max-w-3xl text-xl leading-8 font-semibold text-pretty text-slate-950">
              {progress.current_question.question_text}
            </h3>

            <QuestionVoiceTimerBar
              key={progress.current_question.id}
              questionId={progress.current_question.id}
              difficulty={progress.current_question.difficulty}
              disabled={submitting}
              onAppendSpeech={(spoken) =>
                setAnswerText((prev) => {
                  const sep = prev.length > 0 && !prev.endsWith(' ') ? ' ' : '';
                  return (prev + sep + spoken).slice(0, 10000);
                })
              }
            />

            <QuestionCoachHint
              key={`hint-${progress.current_question.id}`}
              sessionId={progress.session_id}
              questionId={progress.current_question.id}
              disabled={submitting}
            />

            <div className="mb-4">
              <label className="mb-2 block text-sm font-medium text-slate-700">
                Câu trả lời của bạn (tiếng Việt):
              </label>
              <textarea
                rows={6}
                value={answerText}
                onChange={(e) => setAnswerText(e.target.value)}
                disabled={submitting}
                maxLength={10000}
                placeholder="Nhập câu trả lời chi tiết của bạn vào đây..."
                className="w-full rounded-xl border border-slate-300 bg-slate-50 p-4 text-sm leading-6 text-slate-900 placeholder:text-slate-400 focus:border-blue-600 focus:bg-white focus:ring-4 focus:ring-blue-100 disabled:cursor-not-allowed disabled:bg-slate-100"
              />
              <div className="mt-1 flex justify-end font-mono text-xs text-slate-500 tabular-nums">
                {answerText.length}/10000 ký tự
              </div>
            </div>

            {error && (
              <div role="alert" className="mb-4 rounded-lg border-l-4 border-red-500 bg-red-50 p-3 text-sm text-red-800">
                {error}
              </div>
            )}

            {isFinalQuestion && finalAction && (
              <div className="mb-4 rounded-xl border border-blue-200 bg-blue-50 p-4" role="group" aria-label="Xác nhận nộp bài">
                <p className="font-semibold text-slate-950">Nộp bài và kết thúc buổi luyện?</p>
                <p className="mt-1 text-sm leading-6 text-slate-600">Đây là câu cuối. Sau khi nộp, bạn sẽ xem lại bài làm ở trang Kết quả và không thể sửa câu trả lời.</p>
                <div className="mt-4 flex flex-wrap gap-3">
                  <button type="button" onClick={() => handleSubmitResponse(finalAction === 'skip')} disabled={submitting} className="rounded-lg bg-blue-700 px-5 py-2.5 text-sm font-semibold text-white hover:bg-blue-800 focus-visible:ring-4 focus-visible:ring-blue-200 disabled:opacity-50">
                    {submitting ? 'Đang nộp bài...' : finalAction === 'skip' ? 'Xác nhận bỏ qua và nộp bài' : 'Xác nhận nộp bài'}
                  </button>
                  <button type="button" onClick={() => setFinalAction(null)} disabled={submitting} className="rounded-lg px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-white focus-visible:ring-4 focus-visible:ring-blue-200">Quay lại câu trả lời</button>
                </div>
              </div>
            )}
            {!finalAction && <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
              <button
                onClick={() => isFinalQuestion ? setFinalAction('answer') : handleSubmitResponse(false)}
                disabled={submitting || answerText.trim().length === 0 || answerText.length > 10000}
                className="btn-primary-glow inline-flex items-center justify-center rounded-lg bg-blue-700 px-6 py-2.5 text-sm font-semibold text-white hover:bg-blue-800 focus-visible:ring-4 focus-visible:ring-blue-200 disabled:cursor-not-allowed disabled:bg-slate-300"
              >
                {submitting && <span className="spinner-inline mr-2" aria-hidden="true" />}
                {submitting ? 'Đang lưu...' : isFinalQuestion ? 'Nộp bài' : 'Lưu câu trả lời và sang câu tiếp'}
              </button>

              <button
                onClick={() => isFinalQuestion ? setFinalAction('skip') : handleSubmitResponse(true)}
                disabled={submitting}
                className="rounded-lg px-5 py-2.5 text-sm font-semibold text-slate-600 hover:bg-slate-100 hover:text-slate-900 focus-visible:ring-4 focus-visible:ring-slate-200 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {isFinalQuestion ? 'Bỏ qua câu cuối và nộp bài' : 'Bỏ qua câu này'}
              </button>
            </div>}
          </article>
        </div>
      ) : session?.status === 'ready' ? (
        <div className="panel-reveal space-y-6 border-t border-slate-200 pt-8">
          <div className="flex flex-col gap-4 rounded-2xl border border-blue-200/90 bg-gradient-to-r from-blue-50/90 via-blue-50/40 to-white p-6 shadow-xs sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-3.5">
              <div className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-blue-600 text-white shadow-xs shadow-blue-500/20 text-xl">
                ✨
              </div>
              <div>
                <h3 className="text-base font-bold text-slate-950 sm:text-lg">
                  {session.mode_display_title || `Bộ câu hỏi đã sẵn sàng! (Lần luyện số ${session.attempt_number})`}
                </h3>
                <p className="mt-0.5 text-xs sm:text-sm text-slate-600">
                  Gồm 10 câu hỏi phù hợp với hồ sơ ứng tuyển của bạn.
                </p>
              </div>
            </div>
            <button
              onClick={handleStartInterview}
              disabled={loading}
              className="btn-primary-glow inline-flex shrink-0 items-center justify-center gap-2 rounded-xl bg-blue-700 px-6 py-3 text-sm font-bold text-white shadow-sm hover:bg-blue-800 focus-visible:ring-4 focus-visible:ring-blue-200 disabled:bg-slate-300"
            >
              {loading && <span className="spinner-inline mr-2" aria-hidden="true" />}
              {loading ? 'Đang bắt đầu...' : 'Bắt đầu làm bài'}
            </button>
          </div>

          {error && (
            <div role="alert" className="rounded-lg border-l-4 border-red-500 bg-red-50 p-3 text-sm text-red-800">
              {error}
            </div>
          )}

        </div>
      ) : session?.status === 'generation_failed' ? (
        <div className="rounded-2xl border border-slate-200/90 bg-white p-6 shadow-xs sm:p-8">
          <h3 className="text-xl font-bold text-slate-950">Chưa tạo được bộ câu hỏi</h3>
          <p className="mt-2 text-sm leading-6 text-slate-600">Lượt luyện này vẫn được giữ lại. Bạn có thể thử tạo câu hỏi một lần nữa.</p>
          {error && (
            <div role="alert" className="mt-4 rounded-xl border-l-4 border-red-500 bg-red-50 p-3.5 text-sm text-red-800">
              {error}
            </div>
          )}
          <label className="mt-5 flex items-start gap-3 text-sm leading-6 text-slate-700">
            <input type="checkbox" checked={consent} onChange={(event) => setConsent(event.target.checked)} disabled={loading} className="mt-1 size-4 rounded border-slate-300 text-blue-700 focus:ring-blue-200" />
            Tôi đồng ý gửi lại dữ liệu hồ sơ để AI tạo bộ câu hỏi.
          </label>
          <div className="mt-5">
            <button
              onClick={handleRetryGeneration}
              disabled={!consent || loading}
              className="btn-primary-glow rounded-xl bg-blue-700 px-6 py-3 text-sm font-bold text-white hover:bg-blue-800 focus-visible:ring-4 focus-visible:ring-blue-200 disabled:cursor-not-allowed disabled:bg-slate-300"
            >
              {loading ? 'Đang tạo lại...' : 'Thử tạo lại câu hỏi'}
            </button>
          </div>
        </div>
      ) : session?.status === 'generating' ? (
        <div className="rounded-2xl bg-blue-50 p-6 text-sm text-blue-900" role="status">Bộ câu hỏi đang được tạo. Vui lòng chờ trong giây lát rồi tải lại trang.</div>
      ) : (
        <div className="rounded-2xl bg-slate-50 p-7">
          <h3 className="text-xl font-bold text-slate-950">Chưa có bài luyện đang mở</h3>
          <p className="mt-2 text-sm leading-6 text-slate-600">Chọn chế độ và tạo bộ câu hỏi trước khi bắt đầu trả lời.</p>
          <Link href="/practice" className="mt-5 inline-flex rounded-lg bg-blue-700 px-5 py-2.5 text-sm font-semibold text-white hover:bg-blue-800 focus-visible:ring-4 focus-visible:ring-blue-200">Chọn bài luyện →</Link>
        </div>
      )}
    </section>
  );
}
