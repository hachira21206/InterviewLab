'use client';
import { useState, useEffect } from 'react';
import {
  PracticeMode,
  QuestionCategory,
  WeaknessRecommendationResponse,
  isWeaknessRecommendationResponse,
  CATEGORY_LABELS,
  VALID_QUESTION_CATEGORIES,
} from '../types/interview';

interface Props {
  applicationId: string;
  practiceMode: PracticeMode;
  onPracticeModeChange: (mode: PracticeMode) => void;
  focusCategory: QuestionCategory;
  onFocusCategoryChange: (category: QuestionCategory) => void;
  disabled?: boolean;
}

const CATEGORY_META: Record<
  QuestionCategory,
  {
    icon: string;
    keywords: string;
  }
> = {
  database: {
    icon: '💾',
    keywords: 'SQL, Indexing, Transaction ACID, Query Optimization',
  },
  backend_fundamentals: {
    icon: '⚙️',
    keywords: 'OOP, Concurrency, Cấu trúc dữ liệu, Memory, Async I/O',
  },
  api_web_design: {
    icon: '🌐',
    keywords: 'RESTful API, Auth JWT, Caching Redis, HTTP Architecture',
  },
  cv_project_experience: {
    icon: '💼',
    keywords: 'Tech stack thực tế, Kiến trúc dự án, Giải pháp kỹ thuật',
  },
  debugging_problem_solving: {
    icon: '🔍',
    keywords: 'Log analysis, Root Cause (RCA), Profiling, Xử lý sự cố',
  },
  behavioral_teamwork: {
    icon: '🤝',
    keywords: 'Giao tiếp kỹ thuật, Code review, Xử lý xung đột, Agile',
  },
};

export default function PracticeModeSelector({
  applicationId,
  practiceMode,
  onPracticeModeChange,
  focusCategory,
  onFocusCategoryChange,
  disabled = false,
}: Props) {
  const [weaknessRec, setWeaknessRec] = useState<WeaknessRecommendationResponse | null>(null);
  const [loadingWeakness, setLoadingWeakness] = useState(false);

  useEffect(() => {
    let active = true;
    const abortController = new AbortController();

    const fetchWeakness = async () => {
      setWeaknessRec(null);
      setLoadingWeakness(true);
      try {
        const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://127.0.0.1:8000';
        const res = await fetch(
          `${backendUrl}/api/v1/job-applications/${applicationId}/interview-sessions/weakness-recommendation`,
          { signal: abortController.signal }
        );

        if (!res.ok) {
          if (active) {
            setWeaknessRec(null);
          }
          return;
        }

        const contentType = res.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
          if (active) {
            setWeaknessRec(null);
          }
          return;
        }

        const data = (await res.json()) as unknown;

        if (active) {
          if (isWeaknessRecommendationResponse(data)) {
            setWeaknessRec(data);
          } else {
            setWeaknessRec(null);
          }
        }
      } catch (err: unknown) {
        if (err instanceof Error && err.name === 'AbortError') return;
        if (active) {
          setWeaknessRec(null);
        }
      } finally {
        if (active) {
          setLoadingWeakness(false);
        }
      }
    };

    void fetchWeakness();

    return () => {
      active = false;
      abortController.abort();
    };
  }, [applicationId]);

  useEffect(() => {
    if (practiceMode === 'weakness_recovery' && !loadingWeakness && (!weaknessRec || !weaknessRec.available)) {
      onPracticeModeChange('full_mock');
    }
  }, [weaknessRec, loadingWeakness, practiceMode, onPracticeModeChange]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <label className="text-sm font-bold text-slate-900 tracking-tight flex items-center gap-2">
          <span>Chọn chế độ luyện tập:</span>
        </label>
        <span className="text-xs text-slate-500 font-medium">10 câu hỏi / buổi</span>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {/* Mode 1: Full mock */}
        <div
          onClick={() => !disabled && onPracticeModeChange('full_mock')}
          className={`group relative flex flex-col justify-between rounded-xl border p-4 transition-all duration-200 select-none ${
            practiceMode === 'full_mock'
              ? 'border-blue-600 bg-blue-50/80 shadow-xs ring-2 ring-blue-500/20'
              : 'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50/80'
          } ${disabled ? 'cursor-not-allowed opacity-60' : 'cursor-pointer'}`}
        >
          <div>
            <div className="flex items-start justify-between gap-2">
              <div className="flex items-center gap-2.5">
                <input
                  type="radio"
                  name={`practice_mode_${applicationId}`}
                  value="full_mock"
                  checked={practiceMode === 'full_mock'}
                  onChange={() => onPracticeModeChange('full_mock')}
                  disabled={disabled}
                  className="size-4 text-blue-700 focus:ring-blue-500"
                />
                <span className="font-bold text-slate-900 text-sm">
                  Phỏng vấn tổng hợp
                </span>
              </div>
              <span className="text-base" aria-hidden="true">🎯</span>
            </div>
            <p className="mt-2 text-xs leading-5 text-slate-600">
              Bao quát toàn diện 10 câu hỏi thuộc 6 mảng kỹ thuật cốt lõi theo CV và JD.
            </p>
          </div>
          <div className="mt-3 pt-2.5 border-t border-slate-200/60 flex items-center justify-between text-[11px] font-medium text-slate-500">
            <span>Phân bổ cân bằng</span>
            <span className="rounded bg-slate-100 px-1.5 py-0.5 text-slate-700">Mặc định</span>
          </div>
        </div>

        {/* Mode 2: Focus category */}
        <div
          onClick={() => !disabled && onPracticeModeChange('focus_category')}
          className={`group relative flex flex-col justify-between rounded-xl border p-4 transition-all duration-200 select-none ${
            practiceMode === 'focus_category'
              ? 'border-blue-600 bg-blue-50/80 shadow-xs ring-2 ring-blue-500/20'
              : 'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50/80'
          } ${disabled ? 'cursor-not-allowed opacity-60' : 'cursor-pointer'}`}
        >
          <div>
            <div className="flex items-start justify-between gap-2">
              <div className="flex items-center gap-2.5">
                <input
                  type="radio"
                  name={`practice_mode_${applicationId}`}
                  value="focus_category"
                  checked={practiceMode === 'focus_category'}
                  onChange={() => onPracticeModeChange('focus_category')}
                  disabled={disabled}
                  className="size-4 text-blue-700 focus:ring-blue-500"
                />
                <span className="font-bold text-slate-900 text-sm">
                  Luyện theo chuyên đề
                </span>
              </div>
              <span className="text-base" aria-hidden="true">🔍</span>
            </div>
            <p className="mt-2 text-xs leading-5 text-slate-600">
              Tập trung sâu 5 câu vào chuyên đề bạn chọn kèm 5 câu bổ trợ tự nhiên.
            </p>
          </div>
          <div className="mt-3 pt-2.5 border-t border-slate-200/60 flex items-center justify-between text-[11px] font-medium text-blue-700">
            <span>5 câu sâu + 5 câu bổ trợ</span>
            <span className="rounded bg-blue-100 px-1.5 py-0.5 text-blue-800 font-semibold">Tự chọn</span>
          </div>
        </div>

        {/* Mode 3: Weakness recovery */}
        <div
          onClick={() => {
            if (!disabled && weaknessRec?.available && !loadingWeakness) {
              onPracticeModeChange('weakness_recovery');
            }
          }}
          className={`group relative flex flex-col justify-between rounded-xl border p-4 transition-all duration-200 select-none ${
            weaknessRec?.available && !disabled && !loadingWeakness ? 'cursor-pointer' : 'cursor-not-allowed opacity-60'
          } ${
            practiceMode === 'weakness_recovery'
              ? 'border-amber-600 bg-amber-50/80 shadow-xs ring-2 ring-amber-500/20'
              : 'border-slate-200 bg-white hover:border-slate-300'
          }`}
        >
          <div>
            <div className="flex items-start justify-between gap-2">
              <div className="flex items-center gap-2.5">
                <input
                  type="radio"
                  name={`practice_mode_${applicationId}`}
                  value="weakness_recovery"
                  checked={practiceMode === 'weakness_recovery'}
                  onChange={() => {
                    if (weaknessRec?.available && !loadingWeakness) onPracticeModeChange('weakness_recovery');
                  }}
                  disabled={disabled || !weaknessRec?.available || loadingWeakness}
                  className="size-4 text-amber-600 focus:ring-amber-500 disabled:opacity-50"
                />
                <span className="font-bold text-slate-900 text-sm">
                  Luyện bù điểm yếu
                </span>
              </div>
              <span className="text-base" aria-hidden="true">📈</span>
            </div>
            <div className="mt-2 text-xs leading-5">
              {loadingWeakness ? (
                <span className="text-slate-500 flex items-center gap-1.5">
                  <span className="size-2 rounded-full bg-amber-500 animate-ping" />
                  Đang kiểm tra lịch sử...
                </span>
              ) : weaknessRec?.available ? (
                <div className="space-y-1">
                  <p className="text-amber-900 font-semibold">
                    Đề xuất: {weaknessRec.category_label}
                  </p>
                  {weaknessRec.average_score !== null && (
                    <div className="flex items-center gap-2">
                      <span className="text-amber-700 text-[11px] font-bold">
                        Điểm TB: {weaknessRec.average_score.toFixed(1)}/10
                      </span>
                      <span className="text-[10px] text-amber-800 bg-amber-100 rounded px-1.5 py-0.2">
                        Từ {weaknessRec.evaluated_sessions_count} lần luyện
                      </span>
                    </div>
                  )}
                </div>
              ) : (
                <p className="text-slate-500">
                  Chưa đủ dữ liệu. Hoàn thành ít nhất 1 buổi phỏng vấn có đánh giá để mở khóa.
                </p>
              )}
            </div>
          </div>
          <div className="mt-3 pt-2.5 border-t border-slate-200/60 flex items-center justify-between text-[11px] font-medium text-amber-700">
            <span>Hệ thống phân tích</span>
            <span className="rounded bg-amber-100 px-1.5 py-0.5 text-amber-800 font-semibold">Tự động</span>
          </div>
        </div>
      </div>

      {/* Category selector visible when focus_category is chosen */}
      {practiceMode === 'focus_category' && (
        <div className="mt-4 rounded-2xl border border-blue-200 bg-gradient-to-b from-blue-50/70 to-slate-50/50 p-4.5 sm:p-5 shadow-xs transition-all">
          <div className="mb-3.5 flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-xs font-bold text-blue-950 uppercase tracking-wider flex items-center gap-1.5">
                <span>🎯 Chọn chuyên đề muốn tập trung rèn luyện:</span>
              </p>
              <p className="text-[11px] text-blue-800/80">
                Nhấp trực tiếp vào chuyên đề bên dưới để chọn:
              </p>
            </div>
            <span className="text-xs font-semibold text-blue-700 bg-blue-100/70 rounded-full px-2.5 py-0.5 w-fit">
              5 câu trọng tâm + 5 câu bổ trợ
            </span>
          </div>

          {/* Interactive grid of 6 topic cards */}
          <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
            {VALID_QUESTION_CATEGORIES.map((cat) => {
              const isSelected = focusCategory === cat;
              const meta = CATEGORY_META[cat];
              return (
                <button
                  key={cat}
                  type="button"
                  onClick={() => !disabled && onFocusCategoryChange(cat)}
                  disabled={disabled}
                  className={`group relative flex items-start gap-3 rounded-xl border p-3 text-left transition-all duration-150 select-none ${
                    isSelected
                      ? 'border-blue-600 bg-white shadow-xs ring-2 ring-blue-500/25'
                      : 'border-slate-200 bg-white/90 hover:border-blue-300 hover:bg-white hover:shadow-xs'
                  } ${disabled ? 'cursor-not-allowed opacity-60' : 'cursor-pointer'}`}
                >
                  <div className={`flex size-9 shrink-0 items-center justify-center rounded-lg text-lg shadow-2xs transition-transform group-hover:scale-105 ${
                    isSelected ? 'bg-blue-100/80' : 'bg-slate-100'
                  }`}>
                    {meta.icon}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-1">
                      <span className={`text-xs font-bold leading-5 ${isSelected ? 'text-blue-900' : 'text-slate-900'}`}>
                        {CATEGORY_LABELS[cat]}
                      </span>
                      {isSelected && (
                        <span className="flex size-4 shrink-0 items-center justify-center rounded-full bg-blue-600 text-[10px] font-bold text-white shadow-xs">
                          ✓
                        </span>
                      )}
                    </div>
                    <p className="mt-0.5 line-clamp-2 text-[11px] leading-4 text-slate-500">
                      {meta.keywords}
                    </p>
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
