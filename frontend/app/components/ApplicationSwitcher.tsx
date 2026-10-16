'use client';

import { useState, useEffect } from 'react';
import { getStoredPointer, setStoredPointer } from './CVUpload';

export interface ApplicationListItem {
  id: string;
  cv_document_id: string;
  target_role: string;
  job_description: string | null;
  interview_language: string;
  created_at: string;
  updated_at: string;
  cv_document?: {
    original_filename: string;
    status: string;
  } | null;
}

function isApplicationListItem(val: unknown): val is ApplicationListItem {
  if (!val || typeof val !== 'object') return false;
  const obj = val as Record<string, unknown>;
  return (
    typeof obj.id === 'string' &&
    typeof obj.cv_document_id === 'string' &&
    typeof obj.target_role === 'string' &&
    typeof obj.created_at === 'string'
  );
}

interface ApplicationSwitcherProps {
  activeApplicationId: string | null;
  onSelectApplication: (item: ApplicationListItem) => void;
  onDeletedApplication?: (applicationId: string) => void;
  onCreateNew?: () => void;
  compact?: boolean;
}

export default function ApplicationSwitcher({
  activeApplicationId,
  onSelectApplication,
  onDeletedApplication,
  onCreateNew,
  compact = false,
}: ApplicationSwitcherProps) {
  const [items, setItems] = useState<ApplicationListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(!compact);
  const [query, setQuery] = useState('');
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);
  const [deleteCandidate, setDeleteCandidate] = useState<ApplicationListItem | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    const fetchList = async () => {
      try {
        let backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
        if (backendUrl.endsWith('/')) backendUrl = backendUrl.slice(0, -1);

        const res = await fetch(`${backendUrl}/api/v1/job-applications?limit=20`, {
          signal: controller.signal,
        });
        if (!res.ok) return;
        const data = (await res.json()) as unknown;
        if (Array.isArray(data) && data.every(isApplicationListItem)) {
          setItems(data);
        }
      } catch {
        // ignore
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    };
    fetchList();
    return () => controller.abort();
  }, [activeApplicationId]);

  const handleSelect = (item: ApplicationListItem) => {
    setStoredPointer({
      version: 1,
      cv_document_id: item.cv_document_id,
      job_application_id: item.id,
    });
    onSelectApplication(item);
    if (compact) {
      setExpanded(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteCandidate || deleting) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      let backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
      if (backendUrl.endsWith('/')) backendUrl = backendUrl.slice(0, -1);
      const response = await fetch(`${backendUrl}/api/v1/job-applications/${deleteCandidate.id}`, {
        method: 'DELETE',
      });
      if (!response.ok) {
        let message = 'Không thể xóa hồ sơ. Vui lòng thử lại.';
        try {
          const body = (await response.json()) as { detail?: unknown };
          if (typeof body.detail === 'string') message = body.detail;
        } catch {
          // Keep the safe default when the server response is not JSON.
        }
        setDeleteError(message);
        return;
      }
      const deletedId = deleteCandidate.id;
      setItems((previous) => previous.filter((item) => item.id !== deletedId));
      setDeleteCandidate(null);
      setOpenMenuId(null);
      if (currentPointer === deletedId) setStoredPointer(null);
      onDeletedApplication?.(deletedId);
    } catch {
      setDeleteError('Lỗi kết nối khi xóa hồ sơ. Vui lòng thử lại.');
    } finally {
      setDeleting(false);
    }
  };

  if (loading || items.length === 0) {
    return null;
  }

  const currentPointer = activeApplicationId || getStoredPointer()?.job_application_id || null;
  const activeItem = items.find((i) => i.id === currentPointer);
  const normalizedQuery = query.trim().toLocaleLowerCase('vi-VN');
  const filteredItems = normalizedQuery
    ? items.filter((item) => `${item.cv_document?.original_filename || ''} ${item.target_role}`.toLocaleLowerCase('vi-VN').includes(normalizedQuery))
    : items;

  return (
    <div className="mb-6 rounded-2xl border border-slate-200 bg-white/95 p-4 shadow-xs transition-all">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <span className="inline-flex size-8 items-center justify-center rounded-lg bg-blue-50 text-sm text-blue-700">
            🗂️
          </span>
          <div>
            <p className="text-xs font-bold tracking-wider text-blue-700 uppercase">
              Quản lý Hồ sơ ứng tuyển ({items.length})
            </p>
            <p className="text-xs text-slate-600">
              {activeItem
                ? `Đang chọn: ${activeItem.cv_document?.original_filename || 'CV'} (${new Date(activeItem.created_at).toLocaleDateString('vi-VN')})`
                : 'Chọn một hồ sơ đã tạo để tiếp tục hoặc tạo hồ sơ mới'}
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {onCreateNew && (
            <button
              type="button"
              onClick={onCreateNew}
              className="rounded-lg border border-blue-200 bg-blue-50 px-3 py-1.5 text-xs font-semibold text-blue-800 hover:bg-blue-100"
            >
              + Tạo hồ sơ CV mới
            </button>
          )}
          <button
            type="button"
            onClick={() => setExpanded((prev) => !prev)}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-100"
          >
            <span>{expanded ? 'Thu gọn danh sách' : `Đổi hồ sơ khác (${items.length})`}</span>
            <svg
              className={`size-3.5 text-slate-500 transition-transform duration-200 ${expanded ? 'rotate-180' : ''}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2.5}
              aria-hidden="true"
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
            </svg>
          </button>
        </div>
      </div>

      {expanded && (
        <div className="panel-reveal mt-3 border-t border-slate-100 pt-3.5">
          <label className="sr-only" htmlFor="application-search">Tìm hồ sơ</label>
          <input
            id="application-search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Tìm theo tên CV hoặc vị trí..."
            className="mb-3 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-800 placeholder:text-slate-400 focus:border-blue-500 focus:bg-white focus:ring-4 focus:ring-blue-100"
          />
          {filteredItems.length === 0 ? (
            <p className="rounded-lg bg-slate-50 px-3 py-4 text-center text-xs text-slate-500">Không tìm thấy hồ sơ phù hợp.</p>
          ) : (
          <div className="grid max-h-64 grid-cols-1 gap-2.5 overflow-y-auto sm:grid-cols-2">
          {filteredItems.map((item) => {
            const isSelected = item.id === currentPointer;
            return (
              <div
                key={item.id}
                className={`interactive-card relative flex items-center justify-between gap-3 rounded-xl border p-3 ${
                  isSelected
                    ? 'border-blue-400 bg-blue-50/70'
                    : 'border-slate-200 bg-slate-50/50 hover:bg-white'
                }`}
              >
                <div className="min-w-0">
                  <p className="truncate text-xs font-bold text-slate-900">
                    {item.cv_document?.original_filename || `Hồ sơ #${item.id.slice(0, 8)}`}
                  </p>
                  <p className="mt-0.5 text-[11px] text-slate-500">
                    {item.target_role} · {item.job_description ? 'Có JD' : 'Không có JD'}
                  </p>
                  <p className="text-[11px] text-slate-400">
                    Tạo lúc: {new Date(item.created_at).toLocaleString('vi-VN')}
                  </p>
                </div>

                <div className="flex shrink-0 items-center gap-1.5">
                  {isSelected ? (
                    <span className="rounded-md bg-blue-700 px-2.5 py-1 text-[11px] font-semibold text-white">
                      Đang mở
                    </span>
                  ) : (
                    <button
                      type="button"
                      onClick={() => handleSelect(item)}
                      className="rounded-md border border-blue-200 bg-white px-2.5 py-1 text-[11px] font-semibold text-blue-700 hover:bg-blue-50"
                    >
                      Tiếp tục
                    </button>
                  )}
                  <button
                    type="button"
                    aria-label={`Mở thao tác cho ${item.cv_document?.original_filename || 'hồ sơ'}`}
                    aria-expanded={openMenuId === item.id}
                    onClick={() => setOpenMenuId((current) => current === item.id ? null : item.id)}
                    className="grid size-8 place-items-center rounded-lg text-lg leading-none text-slate-500 hover:bg-slate-200 hover:text-slate-800 focus-visible:ring-4 focus-visible:ring-blue-100"
                  >
                    ⋯
                  </button>
                  {openMenuId === item.id && (
                    <div className="panel-reveal absolute right-3 top-12 z-10 min-w-36 rounded-lg border border-slate-200 bg-white p-1.5 shadow-[0_16px_32px_-20px_rgba(15,23,42,0.45)]">
                      <button
                        type="button"
                        onClick={() => {
                          setDeleteCandidate(item);
                          setDeleteError(null);
                          setOpenMenuId(null);
                        }}
                        className="w-full rounded-md px-3 py-2 text-left text-xs font-semibold text-red-700 hover:bg-red-50 focus-visible:ring-2 focus-visible:ring-red-200"
                      >
                        Xóa hồ sơ…
                      </button>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
          </div>
          )}
        </div>
      )}

      {deleteCandidate && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/35 p-4" role="presentation">
          <section role="dialog" aria-modal="true" aria-labelledby="delete-profile-title" className="panel-reveal w-full max-w-md rounded-2xl border border-slate-200 bg-white p-5 shadow-[0_28px_80px_-28px_rgba(15,23,42,0.55)]">
            <p className="text-xs font-semibold tracking-[0.12em] text-red-700 uppercase">Thao tác không thể hoàn tác</p>
            <h2 id="delete-profile-title" className="mt-1 text-xl font-bold tracking-tight text-slate-950">Xóa hồ sơ này?</h2>
            <p className="mt-3 break-words text-sm font-semibold text-slate-800">{deleteCandidate.cv_document?.original_filename || 'Hồ sơ ứng tuyển'}</p>
            <p className="mt-2 text-sm leading-6 text-slate-600">Các phân tích, lần phỏng vấn, đánh giá và báo cáo liên quan sẽ bị xóa. CV và file gốc chỉ bị xóa khi không còn hồ sơ nào khác dùng chung.</p>
            {deleteError && <p role="alert" className="mt-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">{deleteError}</p>}
            <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
              <button type="button" disabled={deleting} onClick={() => { setDeleteCandidate(null); setDeleteError(null); }} className="rounded-lg px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-100 disabled:opacity-50">Hủy</button>
              <button type="button" disabled={deleting} onClick={handleDelete} className="inline-flex items-center justify-center rounded-lg bg-red-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-red-800 focus-visible:ring-4 focus-visible:ring-red-200 disabled:bg-slate-300">
                {deleting ? 'Đang xóa...' : 'Xóa hồ sơ'}
              </button>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
