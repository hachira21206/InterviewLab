'use client';
import { useState } from 'react';

interface QuestionHintData {
  question_id: string;
  order_index: number;
  category: string;
  difficulty: string;
  interview_goal: string;
  key_concepts: string[];
  answer_structure_tips: string[];
}

function isQuestionHintData(data: unknown): data is QuestionHintData {
  if (!data || typeof data !== 'object') return false;
  const d = data as Record<string, unknown>;
  return (
    typeof d.question_id === 'string' &&
    typeof d.order_index === 'number' &&
    typeof d.interview_goal === 'string' &&
    Array.isArray(d.key_concepts) &&
    Array.isArray(d.answer_structure_tips)
  );
}

interface QuestionCoachHintProps {
  sessionId: string;
  questionId: string;
  disabled: boolean;
}

export default function QuestionCoachHint({
  sessionId,
  questionId,
  disabled,
}: QuestionCoachHintProps) {
  const [hint, setHint] = useState<QuestionHintData | null>(null);
  const [open, setOpen] = useState(false);
  const [showKeyConcepts, setShowKeyConcepts] = useState(false);
  const [assistUsed, setAssistUsed] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleToggleHint = async () => {
    if (open) {
      setOpen(false);
      return;
    }

    if (hint && hint.question_id === questionId) {
      setOpen(true);
      setAssistUsed(true);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://127.0.0.1:8000';
      const res = await fetch(
        `${backendUrl}/api/v1/interview-sessions/${sessionId}/questions/${questionId}/hint`
      );
      if (!res.ok) {
        setError('Không thể tải gợi ý cho câu hỏi này.');
        return;
      }
      const data = (await res.json()) as unknown;
      if (isQuestionHintData(data)) {
        setHint(data);
        setOpen(true);
        setAssistUsed(true);
      } else {
        setError('Dữ liệu gợi ý không hợp lệ.');
      }
    } catch {
      setError('Lỗi kết nối khi tải gợi ý.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mb-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <button
          type="button"
          onClick={handleToggleHint}
          disabled={disabled || loading}
          className={`inline-flex items-center gap-2 rounded-lg border px-3.5 py-1.5 text-xs font-semibold transition-all ${
            open
              ? 'border-indigo-300 bg-indigo-100 text-indigo-950 shadow-xs'
              : 'border-indigo-200 bg-indigo-50/80 text-indigo-800 hover:bg-indigo-100'
          } disabled:cursor-not-allowed disabled:opacity-50`}
        >
          {loading ? <span className="spinner-inline" aria-hidden="true" /> : <span>💡</span>}
          <span>
            {loading
              ? 'Đang tải gợi ý...'
              : open
              ? 'Ẩn gợi ý Trợ giảng'
              : 'Gợi ý hướng trả lời (Chế độ Trợ giảng)'}
          </span>
          {!loading && (
            <svg
              className={`size-3.5 text-indigo-600 transition-transform duration-200 ${open ? 'rotate-180' : ''}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2.5}
              aria-hidden="true"
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
            </svg>
          )}
        </button>
        {assistUsed && (
          <span className="rounded-md border border-indigo-200 bg-white px-2 py-1 text-[11px] font-semibold text-indigo-700">
            Đã dùng trợ giảng
          </span>
        )}
      </div>

      {error && (
        <p className="panel-reveal mt-2 text-xs text-red-700">{error}</p>
      )}

      {open && hint && (
        <div className="panel-reveal mt-3 space-y-3 rounded-xl border border-indigo-200 bg-indigo-50/55 p-4 text-xs text-slate-800 shadow-xs" aria-live="polite">
          <div>
            <p className="font-semibold text-indigo-950">🎯 Mục tiêu người phỏng vấn muốn đánh giá:</p>
            <p className="mt-1 leading-5 text-slate-700">{hint.interview_goal}</p>
          </div>

          {hint.answer_structure_tips.length > 0 && (
            <div>
              <p className="font-semibold text-indigo-950">🧭 Bố cục trả lời gợi ý:</p>
              <ol className="mt-1 list-decimal space-y-1 pl-5 leading-5 text-slate-700">
                {hint.answer_structure_tips.map((tip, idx) => (
                  <li key={idx}>{tip}</li>
                ))}
              </ol>
            </div>
          )}

          {hint.key_concepts.length > 0 && (
            <div className="border-t border-indigo-100 pt-2.5">
              {!showKeyConcepts ? (
                <button
                  type="button"
                  onClick={() => setShowKeyConcepts(true)}
                  className="font-semibold text-indigo-700 underline hover:text-indigo-900"
                >
                  🔑 Xem thêm các ý cốt lõi / từ khóa kỹ thuật nên đề cập ({hint.key_concepts.length} ý)
                </button>
              ) : (
                <div className="panel-reveal">
                  <div className="flex items-center justify-between">
                    <p className="font-semibold text-indigo-950">🔑 Các ý cốt lõi nên đề cập trong câu trả lời:</p>
                    <button
                      type="button"
                      onClick={() => setShowKeyConcepts(false)}
                      className="text-indigo-700 hover:underline"
                    >
                      Thu gọn
                    </button>
                  </div>
                  <ul className="mt-1.5 list-disc space-y-1 pl-5 leading-5 text-slate-700">
                    {hint.key_concepts.map((concept, idx) => (
                      <li key={idx}>{concept}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
