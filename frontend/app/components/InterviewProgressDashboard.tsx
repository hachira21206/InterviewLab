'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  InterviewProgressReportResponse,
  isInterviewProgressReportResponse,
} from '../types/progress';

interface InterviewProgressDashboardProps {
  applicationId: string;
}

const CATEGORY_NAMES: Record<string, string> = {
  backend_fundamentals: 'Kiến thức cốt lõi Backend',
  cv_project_experience: 'Kinh nghiệm dự án & CV',
  database: 'Cơ sở dữ liệu & Tối ưu hóa',
  api_web_design: 'Thiết kế API & Web Architecture',
  debugging_problem_solving: 'Debug & Xử lý sự cố',
  behavioral_teamwork: 'Kỹ năng mềm & Làm việc nhóm',
};

const READINESS_LABELS: Record<string, string> = {
  needs_foundation: 'Cần củng cố nền tảng',
  developing: 'Đang phát triển (Developing)',
  intern_ready: 'Sẵn sàng Intern (Intern-Ready)',
  strong_intern_candidate: 'Ứng viên Intern xuất sắc',
};

export default function InterviewProgressDashboard({ applicationId }: InterviewProgressDashboardProps) {
  const [data, setData] = useState<InterviewProgressReportResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const isMountedRef = useRef<boolean>(true);

  const fetchProgress = useCallback(async () => {
    if (!applicationId) return;

    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    setLoading(true);
    setError(null);

    try {
      const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
      const res = await fetch(`${backendUrl}/api/v1/job-applications/${applicationId}/interview-progress`, {
        signal: controller.signal,
      });

      const contentType = res.headers.get('content-type') || '';

      if (!res.ok) {
        if (contentType.includes('application/json')) {
          const errData = (await res.json()) as { detail?: string };
          throw new Error(errData.detail || `Lỗi máy chủ HTTP ${res.status}`);
        } else {
          throw new Error(`Máy chủ phản hồi không đúng định dạng JSON (HTTP ${res.status}).`);
        }
      }

      if (!contentType.includes('application/json')) {
        throw new Error('Phản hồi từ máy chủ không phải JSON hợp lệ.');
      }

      const json = (await res.json()) as unknown;
      if (!isInterviewProgressReportResponse(json, applicationId)) {
        throw new Error('Phản hồi tiến độ không đúng định dạng chuẩn.');
      }

      if (!controller.signal.aborted && isMountedRef.current) {
        setData(json);
        setError(null);
      }
    } catch (err: unknown) {
      if (err instanceof Error) {
        if (err.name === 'AbortError') {
          return;
        }
        if (isMountedRef.current) {
          setError(err.message);
        }
      } else {
        if (isMountedRef.current) {
          setError('Lỗi không xác định khi tải dữ liệu tiến độ.');
        }
      }
      if (isMountedRef.current) {
        setData(null);
      }
    } finally {
      if (!controller.signal.aborted && isMountedRef.current) {
        setLoading(false);
      }
    }
  }, [applicationId]);

  useEffect(() => {
    isMountedRef.current = true;
    const prevAbort = abortControllerRef.current;

    void Promise.resolve().then(() => {
      if (isMountedRef.current) {
        void fetchProgress();
      }
    });

    return () => {
      isMountedRef.current = false;
      prevAbort?.abort();
      abortControllerRef.current?.abort();
    };
  }, [fetchProgress]);

  const renderDeltaBadge = (delta: number, label: string) => {
    const isPositive = delta > 0;
    const isNegative = delta < 0;
    const formatted = isPositive ? `+${delta}` : `${delta}`;

    let colorClasses = 'bg-gray-100 text-gray-700 border-gray-300';
    let icon = '→';
    let directionText = 'Không đổi';

    if (isPositive) {
      colorClasses = 'bg-green-50 text-green-700 border-green-300';
      icon = '↑';
      directionText = 'Tăng';
    } else if (isNegative) {
      colorClasses = 'bg-red-50 text-red-700 border-red-300';
      icon = '↓';
      directionText = 'Giảm';
    }

    return (
      <span
        className={`inline-flex items-center gap-1 px-2.5 py-1 rounded border text-xs font-semibold ${colorClasses}`}
        title={`${label}: ${directionText} ${formatted}`}
      >
        <span>{icon}</span>
        <span>{directionText}: {formatted}</span>
      </span>
    );
  };

  const renderTrendSvg = () => {
    if (!data || data.trend.length === 0) return null;

    const width = 500;
    const height = 180;
    const paddingX = 40;
    const paddingTop = 20;
    const paddingBottom = 35;
    const chartHeight = height - paddingTop - paddingBottom;
    const chartWidth = width - paddingX * 2;

    const points = data.trend.map((item, index) => {
      const x =
        data.trend.length === 1
          ? width / 2
          : paddingX + (index / (data.trend.length - 1)) * chartWidth;
      const y = paddingTop + chartHeight - (item.total_score / 100) * chartHeight;
      return { x, y, item };
    });

    const pathD = points.reduce((acc, curr, index) => {
      return index === 0 ? `M ${curr.x} ${curr.y}` : `${acc} L ${curr.x} ${curr.y}`;
    }, '');

    return (
      <div className="w-full rounded-xl bg-slate-50 p-4 sm:p-5">
        <h4 className="mb-3 text-sm font-semibold text-slate-800">Xu hướng điểm tổng qua các lần luyện (0 - 100)</h4>
        <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-auto overflow-visible" aria-label="Biểu đồ tiến bộ">
          {/* Y-axis grid lines (0, 25, 50, 75, 100) */}
          {[0, 25, 50, 75, 100].map((score) => {
            const y = paddingTop + chartHeight - (score / 100) * chartHeight;
            return (
              <g key={`grid-${score}`}>
                <line x1={paddingX} y1={y} x2={width - paddingX} y2={y} stroke="#E5E7EB" strokeDasharray="3 3" />
                <text x={paddingX - 8} y={y + 4} textAnchor="end" fontSize="10" fill="#9CA3AF">
                  {score}
                </text>
              </g>
            );
          })}

          {/* Line Connecting Points */}
          {data.trend.length > 1 && (
            <path d={pathD} fill="none" stroke="#2563EB" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
          )}

          {/* Data Points and Labels */}
          {points.map(({ x, y, item }) => (
            <g key={`point-${item.session_id}`}>
              <circle cx={x} cy={y} r="5" fill="#2563EB" stroke="#FFFFFF" strokeWidth="2" className="cursor-pointer">
                <title>{`Lần ${item.attempt_number}: ${item.total_score} điểm`}</title>
              </circle>
              {/* Score text label */}
              <text x={x} y={y - 10} textAnchor="middle" fontSize="11" fontWeight="bold" fill="#1E40AF">
                {item.total_score}
              </text>
              {/* Attempt X label */}
              <text x={x} y={height - 8} textAnchor="middle" fontSize="11" fill="#4B5563">
                Lần {item.attempt_number}
              </text>
            </g>
          ))}
        </svg>
      </div>
    );
  };

  return (
    <section className="space-y-6 border-t border-slate-200 pt-8" aria-labelledby="progress-dashboard-title">
      <div className="flex items-start justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <p className="text-xs font-semibold tracking-[0.12em] text-blue-700 uppercase">Xu hướng dài hạn</p>
          <h3 id="progress-dashboard-title" className="mt-1 text-xl font-bold tracking-tight text-slate-950">Dashboard Tiến bộ & So sánh phỏng vấn</h3>
          <p className="mt-1 text-xs leading-5 text-slate-500">
            Theo dõi xu hướng điểm số và đánh giá mức độ tiến bộ qua các lần luyện tập độc lập.
          </p>
        </div>
        <button
          onClick={fetchProgress}
          disabled={loading}
          className="shrink-0 rounded-md px-3 py-1.5 text-xs font-medium text-blue-700 hover:bg-blue-50 focus-visible:ring-4 focus-visible:ring-blue-100 disabled:opacity-50"
        >
          {loading ? 'Đang tải...' : 'Cập nhật tiến độ'}
        </button>
      </div>

      {/* Loading state */}
      {loading && (
        <div className="py-8 text-center text-sm text-slate-500">
          <p className="animate-pulse">Đang phân tích số liệu tiến bộ phỏng vấn...</p>
        </div>
      )}

      {/* Error state */}
      {!loading && error && (
        <div role="alert" className="rounded-lg border-l-4 border-red-500 bg-red-50 p-4 text-sm text-red-800">
          <p className="font-semibold">Không thể tải dữ liệu tiến độ</p>
          <p className="text-xs mt-1">{error}</p>
        </div>
      )}

      {/* Data display */}
      {!loading && !error && data && (
        <div className="space-y-6">
          {/* 1. Overview cards */}
          <div className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-slate-200 bg-slate-200 sm:grid-cols-4">
            <div className="bg-white p-4">
              <span className="text-xs text-slate-500">Tổng số lần luyện</span>
              <p className="mt-1 font-mono text-2xl font-bold text-slate-900 tabular-nums">{data.total_attempts}</p>
            </div>
            <div className="bg-white p-4">
              <span className="text-xs text-slate-500">Đã hoàn thành</span>
              <p className="mt-1 font-mono text-2xl font-bold text-slate-900 tabular-nums">{data.completed_attempts}</p>
            </div>
            <div className="bg-white p-4">
              <span className="text-xs text-slate-500">Đã có đánh giá</span>
              <p className="mt-1 font-mono text-2xl font-bold text-slate-900 tabular-nums">{data.evaluated_attempts}</p>
            </div>
            <div className="bg-blue-50 p-4">
              <span className="text-xs font-medium text-blue-700">Điểm mới nhất</span>
              <p className="mt-1 font-mono text-2xl font-bold text-blue-800 tabular-nums">
                {data.latest ? `${data.latest.total_score} / 100` : 'Chưa có'}
              </p>
            </div>
          </div>

          {/* Readiness banner if latest available */}
          {data.latest && (
            <div className="flex items-center justify-between border-l-4 border-blue-600 bg-blue-50/70 p-3 text-xs">
              <span className="font-medium text-blue-800">
                Mức độ sẵn sàng mới nhất (Lần luyện số {data.latest.attempt_number}):
              </span>
              <span className="rounded-md bg-white px-2.5 py-1 font-bold text-blue-950">
                {READINESS_LABELS[data.latest.readiness_level] || data.latest.readiness_level}
              </span>
            </div>
          )}

          {/* No data state */}
          {data.comparison.status === 'no_data' && (
            <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 py-7 text-center text-sm text-slate-500">
              <p className="font-medium text-slate-700">Chưa có dữ liệu đánh giá tiến độ</p>
              <p className="mt-1 text-xs text-slate-500">
                Hãy hoàn tất trả lời câu hỏi và thực hiện đánh giá để bắt đầu theo dõi tiến bộ.
              </p>
            </div>
          )}

          {/* Insufficient data state */}
          {data.comparison.status === 'insufficient_data' && (
            <div className="space-y-4">
              <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-800">
                Bạn đã hoàn thành 1 lần luyện. Luyện tập thêm lần tiếp theo để so sánh mức độ tiến bộ!
              </div>
              {renderTrendSvg()}
            </div>
          )}

          {/* Multi-attempt comparison state */}
          {['improved', 'declined', 'unchanged'].includes(data.comparison.status) && (
            <div className="space-y-6">
              {/* Comparison Section */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Latest vs Previous */}
                {data.comparison.latest_vs_previous && (
                  <div className="space-y-3 rounded-lg bg-slate-50 p-4">
                    <h5 className="text-xs font-bold uppercase tracking-wider text-gray-600">
                      So với lần luyện trước liền kề
                    </h5>
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-gray-600">Điểm tổng (100đ):</span>
                        {renderDeltaBadge(
                          data.comparison.latest_vs_previous.total_score_delta,
                          'Điểm tổng'
                        )}
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-gray-600">Điểm trung bình (10đ):</span>
                        {renderDeltaBadge(
                          data.comparison.latest_vs_previous.average_score_delta,
                          'Điểm TB'
                        )}
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-gray-600">Số câu trả lời:</span>
                        {renderDeltaBadge(
                          data.comparison.latest_vs_previous.answered_count_delta,
                          'Số câu trả lời'
                        )}
                      </div>
                      <div className="flex items-center justify-between pt-1 border-t border-gray-200">
                        <span className="text-xs text-gray-600">Mức độ sẵn sàng:</span>
                        <span className="text-xs font-semibold text-gray-800">
                          {data.comparison.latest_vs_previous.readiness_changed
                            ? data.comparison.latest_vs_previous.readiness_direction === 'improved'
                              ? '↑ Đã nâng cao'
                              : '↓ Giảm mức'
                            : '→ Giữ nguyên mức'}
                        </span>
                      </div>
                    </div>
                  </div>
                )}

                {/* Latest vs First */}
                {data.comparison.latest_vs_first && (
                  <div className="space-y-3 rounded-lg bg-slate-50 p-4">
                    <h5 className="text-xs font-bold uppercase tracking-wider text-gray-600">
                      So với lần luyện đầu tiên
                    </h5>
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-gray-600">Điểm tổng (100đ):</span>
                        {renderDeltaBadge(
                          data.comparison.latest_vs_first.total_score_delta,
                          'Điểm tổng'
                        )}
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-gray-600">Điểm trung bình (10đ):</span>
                        {renderDeltaBadge(
                          data.comparison.latest_vs_first.average_score_delta,
                          'Điểm TB'
                        )}
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-gray-600">Số câu trả lời:</span>
                        {renderDeltaBadge(
                          data.comparison.latest_vs_first.answered_count_delta,
                          'Số câu trả lời'
                        )}
                      </div>
                      <div className="flex items-center justify-between pt-1 border-t border-gray-200">
                        <span className="text-xs text-gray-600">Mức độ sẵn sàng:</span>
                        <span className="text-xs font-semibold text-gray-800">
                          {data.comparison.latest_vs_first.readiness_changed
                            ? data.comparison.latest_vs_first.readiness_direction === 'improved'
                              ? '↑ Đã nâng cao'
                              : '↓ Giảm mức'
                            : '→ Giữ nguyên mức'}
                        </span>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* Trend SVG */}
              {renderTrendSvg()}
            </div>
          )}

          {/* Category Progress Section */}
          {data.category_progress.length > 0 && (
            <div className="space-y-3 pt-2">
              <h4 className="text-sm font-bold text-slate-900">Tiến bộ theo từng nhóm kỹ năng</h4>
              <div className="overflow-x-auto rounded-lg border border-slate-200">
                <table className="min-w-full divide-y divide-slate-200 text-xs tabular-nums">
                  <thead className="bg-slate-50">
                    <tr>
                      <th className="px-3 py-2 text-left font-semibold text-gray-700">Kỹ năng</th>
                      <th className="px-3 py-2 text-center font-semibold text-gray-700">Lần đầu</th>
                      <th className="px-3 py-2 text-center font-semibold text-gray-700">Mới nhất</th>
                      <th className="px-3 py-2 text-center font-semibold text-gray-700">Thay đổi</th>
                      <th className="px-3 py-2 text-center font-semibold text-gray-700">Số lần có dữ liệu</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200 bg-white">
                    {data.category_progress.map((cat) => {
                      const name = CATEGORY_NAMES[cat.category] || cat.category;
                      return (
                        <tr key={cat.category}>
                          <td className="px-3 py-2 font-medium text-gray-800">{name}</td>
                          <td className="px-3 py-2 text-center text-gray-600">
                            {cat.first_score !== null ? `${cat.first_score} / 10` : 'Chưa có dữ liệu'}
                          </td>
                          <td className="px-3 py-2 text-center font-semibold text-blue-700">
                            {cat.latest_score !== null ? `${cat.latest_score} / 10` : 'Chưa có dữ liệu'}
                          </td>
                          <td className="px-3 py-2 text-center">
                            {cat.latest_vs_first_delta !== null
                              ? renderDeltaBadge(cat.latest_vs_first_delta, name)
                              : <span className="text-gray-400">Chưa có dữ liệu</span>}
                          </td>
                          <td className="px-3 py-2 text-center text-gray-600">{cat.attempts_with_data}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
