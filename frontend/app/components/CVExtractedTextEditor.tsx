'use client';

import { useState } from 'react';
import { isCVMetadataResponse, type CVMetadata } from './CVUpload';

interface CVExtractedTextEditorProps {
  cvId: string;
  extractedText: string;
  onUpdated: (updated: CVMetadata) => void;
}

export default function CVExtractedTextEditor({
  cvId,
  extractedText,
  onUpdated,
}: CVExtractedTextEditorProps) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(extractedText);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedNotice, setSavedNotice] = useState(false);

  const handleStartEdit = () => {
    setDraft(extractedText);
    setError(null);
    setSavedNotice(false);
    setEditing(true);
  };

  const handleCancel = () => {
    setDraft(extractedText);
    setError(null);
    setEditing(false);
  };

  const handleSave = async () => {
    const trimmed = draft.trim();
    if (trimmed.length < 50) {
      setError('Nội dung CV phải có ít nhất 50 ký tự.');
      return;
    }
    if (trimmed.length > 30000) {
      setError('Nội dung CV không được vượt quá 30.000 ký tự.');
      return;
    }

    setSaving(true);
    setError(null);
    try {
      let backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
      if (backendUrl.endsWith('/')) backendUrl = backendUrl.slice(0, -1);

      const res = await fetch(`${backendUrl}/api/v1/cv-documents/${cvId}/extracted-text`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ extracted_text: draft }),
      });

      if (!res.ok) {
        let msg = 'Không thể lưu nội dung CV đã chỉnh sửa.';
        try {
          const errData = (await res.json()) as { detail?: unknown };
          if (typeof errData?.detail === 'string') {
            msg = errData.detail;
          }
        } catch {
          // ignore
        }
        setError(msg);
        return;
      }

      const data = (await res.json()) as unknown;
      if (isCVMetadataResponse(data)) {
        onUpdated(data);
        setEditing(false);
        setSavedNotice(true);
      } else {
        setError('Dữ liệu phản hồi từ máy chủ không hợp lệ.');
      }
    } catch {
      setError('Lỗi kết nối khi lưu nội dung CV.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="mt-6">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <p className="text-sm font-semibold text-slate-800">Bản xem trước nội dung CV:</p>
          {savedNotice && !editing && (
            <span className="panel-reveal rounded-md bg-emerald-50 px-2.5 py-0.5 text-xs font-medium text-emerald-700">
              ✓ Đã lưu chỉnh sửa
            </span>
          )}
        </div>

        {!editing && (
          <button
            type="button"
            onClick={handleStartEdit}
            className="inline-flex items-center gap-1.5 rounded-lg border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-800 hover:bg-blue-100"
          >
            ✏️ Chỉnh sửa nội dung trích xuất
          </button>
        )}
      </div>

      {!editing ? (
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-slate-50/70">
          <div className="flex items-center justify-between border-b border-slate-200 bg-white/70 px-4 py-2.5">
            <p className="text-xs font-medium text-slate-600">Nội dung AI sẽ dùng để phân tích</p>
            <span className="font-mono text-[11px] text-slate-500 tabular-nums">{extractedText.length} ký tự</span>
          </div>
          <div
            data-testid="cv-text-preview"
            className="h-48 overflow-y-auto px-4 py-3.5 font-mono text-xs leading-5 text-slate-700 whitespace-pre-wrap"
          >
            {extractedText}
          </div>
        </div>
      ) : (
        <div className="panel-reveal space-y-2.5 rounded-xl border border-blue-200 bg-blue-50/45 p-4 shadow-xs">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <p className="max-w-xl text-xs leading-5 text-slate-600">
              Rà soát lỗi trích xuất, định dạng hoặc kỹ năng/dự án bị thiếu trước khi phân tích AI. Thay đổi chỉ có hiệu lực khi bạn lưu.
            </p>
            <span className="rounded-md bg-white px-2 py-1 text-[11px] font-medium text-blue-700">Bản nháp</span>
          </div>
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            disabled={saving}
            rows={9}
            maxLength={30000}
            className="w-full rounded-lg border border-slate-300 bg-white p-3 font-mono text-xs leading-5 text-slate-800 focus:border-blue-600 focus:ring-4 focus:ring-blue-100 disabled:bg-slate-100"
          />
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="font-mono text-xs text-slate-500 tabular-nums">
              {draft.length} / 30000 ký tự
            </span>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleCancel}
                disabled={saving}
                className="rounded-lg border border-slate-300 bg-white px-3.5 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50"
              >
                Bỏ thay đổi
              </button>
              <button
                type="button"
                onClick={handleSave}
                disabled={saving}
                className="btn-primary-glow inline-flex items-center gap-1.5 rounded-lg bg-blue-700 px-4 py-1.5 text-xs font-semibold text-white hover:bg-blue-800 disabled:bg-slate-300"
              >
                {saving && <span className="spinner-inline" aria-hidden="true" />}
                <span>{saving ? 'Đang lưu...' : 'Lưu nội dung CV'}</span>
              </button>
            </div>
          </div>
          {error && (
            <p className="panel-reveal text-xs font-medium text-red-700">{error}</p>
          )}
        </div>
      )}
    </div>
  );
}
