'use client';
import Link from 'next/link';
import { useState, useEffect, useRef } from 'react';
import InterviewEvaluation from './InterviewEvaluation';
import InterviewHistory from './InterviewHistory';
import InterviewProgressDashboard from './InterviewProgressDashboard';
import QuestionVoiceTimerBar from './QuestionVoiceTimerBar';
import QuestionCoachHint from './QuestionCoachHint';
import {
  SessionStatus,
  QuestionCategory,
  QuestionDifficulty,
  InterviewSessionResponse,
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
  mode?: 'full' | 'interview' | 'result';
}

export default function InterviewQuestions({ applicationId, analysisCompleted, mode = 'full' }: Props) {
  const [session, setSession] = useState<InterviewSessionResponse | null>(null);
  const [progress, setProgress] = useState<InterviewProgressResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [consent, setConsent] = useState(false);
  const [answerText, setAnswerText] = useState('');
  const abortControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!analysisCompleted) return;
    
    const abortController = new AbortController();
    
    const fetchSessionAndProgress = async () => {
      try {
        const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://127.0.0.1:8000';
        const res = await fetch(`${backendUrl}/api/v1/job-applications/${applicationId}/interview-sessions/current`, {
          signal: abortController.signal
        });
        
        if (res.status === 404) return;
        
        const contentType = res.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
           throw new Error('Dữ liệu trả về không hợp lệ.');
        }
        
        const data = await res.json() as unknown;
        if (res.ok) {
          if (isInterviewSessionResponse(data)) {
            setSession(data);
            if (data.status === 'generation_failed') {
               setError(data.error_message || 'Tạo câu hỏi thất bại.');
            } else if (data.status === 'in_progress' || data.status === 'completed') {
              // Fetch latest progress
              const progRes = await fetch(`${backendUrl}/api/v1/interview-sessions/${data.id}/progress`, {
                signal: abortController.signal
              });
              if (progRes.ok) {
                const progData = await progRes.json() as unknown;
                if (isInterviewProgressResponse(progData)) {
                  setProgress(progData);
                }
              }
            }
          }
        }
      } catch (err: unknown) {
        if (err instanceof Error && err.name !== 'AbortError') {
          // ignore
        }
      }
    };
    fetchSessionAndProgress();
    return () => abortController.abort();
  }, [applicationId, analysisCompleted]);

  const loadSessionById = async (sessionId: string) => {
    try {
      const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://127.0.0.1:8000';
      const res = await fetch(`${backendUrl}/api/v1/job-applications/${applicationId}/interview-sessions/${sessionId}`);
      if (!res.ok) return;
      const data = (await res.json()) as unknown;
      if (isInterviewSessionResponse(data)) {
        setSession(data);
        if (data.status === 'in_progress' || data.status === 'completed') {
          const progRes = await fetch(`${backendUrl}/api/v1/interview-sessions/${data.id}/progress`);
          if (progRes.ok) {
            const progData = (await progRes.json()) as unknown;
            if (isInterviewProgressResponse(progData)) {
              setProgress(progData);
            }
          }
        } else {
          setProgress(null);
        }
      }
    } catch {
      // ignore
    }
  };

  useEffect(() => {
    return () => {
      if (abortControllerRef.current) abortControllerRef.current.abort();
    };
  }, []);

  const handleGenerate = async () => {
    if (loading || session?.status === 'generating') return;
    setLoading(true);
    setError(null);
    
    if (abortControllerRef.current) abortControllerRef.current.abort();
    const abortController = new AbortController();
    abortControllerRef.current = abortController;
    
    try {
      const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://127.0.0.1:8000';
      const res = await fetch(`${backendUrl}/api/v1/job-applications/${applicationId}/interview-sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ consent_to_external_ai: consent }),
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
        if (isInterviewSessionResponse(data)) {
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

  return (
    <section className="mt-10 space-y-10 border-t border-slate-200 pt-9" aria-labelledby="interview-workspace-title">
      <div>
        <p className="text-xs font-semibold tracking-[0.12em] text-blue-700 uppercase">04 · Luyện phỏng vấn</p>
        <h2 id="interview-workspace-title" className="mt-1 text-2xl font-bold tracking-tight text-slate-950">Không gian phỏng vấn</h2>
        <p className="mt-2 text-sm leading-6 text-slate-600">Tạo bộ câu hỏi theo hồ sơ, trả lời lần lượt và xem lại toàn bộ nội dung sau khi hoàn thành.</p>
      </div>
      {mode !== 'interview' && (
        <InterviewHistory
          applicationId={applicationId}
          selectedSessionId={session?.id || null}
          onSelectSession={loadSessionById}
          onAttemptCreated={loadSessionById}
        />
      )}
      {mode === 'full' && (
        <>
          <InterviewProgressDashboard applicationId={applicationId} />
        </>
      )}

      {/* 3. Active Session Details / Answering Interface / Transcript */}
      {progress?.status === 'completed' ? (
        <div className="border-t border-slate-200 pt-8">
          <div className="mb-7 border-l-4 border-emerald-500 bg-emerald-50/70 p-5">
            <p className="mb-1 text-xs font-semibold tracking-[0.12em] text-emerald-700 uppercase">Phiên luyện đã hoàn tất</p>
            <h2 className="text-2xl font-bold tracking-tight text-emerald-950">
              Hoàn thành buổi phỏng vấn {session ? `(Lần luyện số ${session.attempt_number})` : ''}
            </h2>
            <p className="mt-2 text-sm leading-6 text-emerald-800">
              Bạn đã hoàn thành toàn bộ {progress.total_questions} câu hỏi phỏng vấn.
            </p>
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
          <InterviewEvaluation
            sessionId={progress.session_id}
            attemptNumber={session?.attempt_number}
            showCompletionLinks={mode === 'interview'}
            userAnswers={Object.fromEntries(
              progress.responses.map((r) => [r.order_index, r.answer_text])
            )}
          />
          {mode === 'result' && (
            <div className="mt-7 border-t border-slate-200 pt-6 text-right">
              <Link href="/progress" className="inline-flex rounded-lg bg-blue-700 px-5 py-2.5 text-sm font-semibold text-white hover:bg-blue-800">Xem tiến bộ qua các lần luyện</Link>
            </div>
          )}
        </div>
      ) : mode === 'result' ? (
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-6 text-center">
          <p className="text-sm font-semibold text-slate-900">Chưa có kết quả hoàn chỉnh để hiển thị</p>
          <p className="mt-2 text-sm leading-6 text-slate-600">Hãy hoàn thành một buổi phỏng vấn, sau đó quay lại đây để xem transcript và đánh giá.</p>
          <Link href="/interview" className="mt-5 inline-flex rounded-lg bg-blue-700 px-5 py-2.5 text-sm font-semibold text-white hover:bg-blue-800">Đi tới phỏng vấn</Link>
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

            <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
              <button
                onClick={() => handleSubmitResponse(false)}
                disabled={submitting || answerText.trim().length === 0 || answerText.length > 10000}
                className="btn-primary-glow inline-flex items-center justify-center rounded-lg bg-blue-700 px-6 py-2.5 text-sm font-semibold text-white hover:bg-blue-800 focus-visible:ring-4 focus-visible:ring-blue-200 disabled:cursor-not-allowed disabled:bg-slate-300"
              >
                {submitting && <span className="spinner-inline mr-2" aria-hidden="true" />}
                {submitting ? 'Đang gửi...' : 'Gửi câu trả lời'}
              </button>

              <button
                onClick={() => handleSubmitResponse(true)}
                disabled={submitting}
                className="rounded-lg px-5 py-2.5 text-sm font-semibold text-slate-600 hover:bg-slate-100 hover:text-slate-900 focus-visible:ring-4 focus-visible:ring-slate-200 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Bỏ qua câu này
              </button>
            </div>
          </article>
        </div>
      ) : session?.status === 'ready' ? (
        <div className="panel-reveal space-y-6 border-t border-slate-200 pt-8">
          <div className="flex flex-col gap-4 rounded-xl border-l-4 border-blue-600 bg-blue-50/70 p-5 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h3 className="font-semibold text-blue-950">
                Bộ câu hỏi đã sẵn sàng! (Lần luyện số {session.attempt_number})
              </h3>
              <p className="mt-1 text-sm text-blue-800">
                Gồm 10 câu hỏi phù hợp với hồ sơ ứng tuyển của bạn.
              </p>
            </div>
            <button
              onClick={handleStartInterview}
              disabled={loading}
              className="btn-primary-glow inline-flex shrink-0 items-center justify-center rounded-lg bg-blue-700 px-6 py-2.5 text-sm font-semibold text-white hover:bg-blue-800 focus-visible:ring-4 focus-visible:ring-blue-200 disabled:bg-slate-300"
            >
              {loading && <span className="spinner-inline mr-2" aria-hidden="true" />}
              {loading ? 'Đang khởi động...' : 'Bắt đầu phỏng vấn'}
            </button>
          </div>

          {error && (
            <div role="alert" className="rounded-lg border-l-4 border-red-500 bg-red-50 p-3 text-sm text-red-800">
              {error}
            </div>
          )}

          <div className="text-xs text-slate-500">Sinh bởi {session.provider}</div>
          {session.questions.map((q) => (
            <article key={q.id} className="border-b border-slate-200 py-4 last:border-0">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <h3 className="text-base leading-6 font-medium text-slate-900">
                  Câu {q.order_index}: {q.question_text}
                </h3>
                <div className="flex shrink-0 gap-2 sm:ml-4">
                  <span className="rounded-md bg-blue-50 px-2 py-1 text-xs font-medium text-blue-700">
                    {q.category}
                  </span>
                  <span
                    className={`rounded-md px-2 py-1 text-xs font-medium ${
                      q.difficulty === 'easy'
                        ? 'bg-green-50 text-green-700'
                        : q.difficulty === 'medium'
                        ? 'bg-yellow-50 text-yellow-700'
                        : 'bg-red-50 text-red-700'
                    }`}
                  >
                    {q.difficulty}
                  </span>
                </div>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <div className="rounded-xl border-t border-slate-200 bg-slate-50 p-5 pt-7 sm:p-6">
          <p className="text-xs font-semibold tracking-[0.12em] text-blue-700 uppercase">Bước tiếp theo</p>
          <h3 className="mt-1 text-xl font-bold tracking-tight text-slate-950">Khởi tạo buổi phỏng vấn</h3>
          <div className="mt-3 text-sm leading-6 text-slate-600">
            <p className="mb-2">
              Nội dung CV và JD sẽ được gửi đến nhà cung cấp AI để sinh bộ câu hỏi phỏng vấn phù hợp.
            </p>
          </div>

          <label className="mt-5 flex cursor-pointer items-start gap-3 border-t border-slate-200 pt-5 group">
            <div className="flex h-5 items-center">
              <input
                type="checkbox"
                checked={consent}
                onChange={(e) => setConsent(e.target.checked)}
                disabled={loading || session?.status === 'generating'}
                className="size-4 rounded border border-slate-300 bg-white text-blue-700 focus:ring-4 focus:ring-blue-200 disabled:opacity-50"
              />
            </div>
            <span className="text-sm leading-6 text-slate-700 group-hover:text-slate-950">
              Tôi đồng ý gửi dữ liệu để tạo bộ câu hỏi phỏng vấn.
            </span>
          </label>

          {error && (
            <div role="alert" className="mt-4 rounded-lg border-l-4 border-red-500 bg-red-50 p-3 text-sm text-red-800">
              {error}
            </div>
          )}

          <button
            onClick={handleGenerate}
            disabled={!consent || loading || session?.status === 'generating'}
            className="btn-primary-glow mt-5 inline-flex w-full items-center justify-center rounded-lg bg-blue-700 px-6 py-2.5 text-sm font-semibold text-white hover:bg-blue-800 focus-visible:ring-4 focus-visible:ring-blue-200 disabled:cursor-not-allowed disabled:bg-slate-300 sm:w-auto"
          >
            {(loading || session?.status === 'generating') && (
              <span className="spinner-inline mr-2" aria-hidden="true" />
            )}
            {loading || session?.status === 'generating'
              ? 'Đang tạo câu hỏi...'
              : session?.status === 'generation_failed'
              ? 'Thử lại'
              : 'Tạo bộ câu hỏi phỏng vấn'}
          </button>
        </div>
      )}
    </section>
  );
}
