'use client';

import Link from 'next/link';
import { useState, useRef, useEffect } from 'react';
import AIAnalysis from './AIAnalysis';
import ApplicationSwitcher from './ApplicationSwitcher';
import CVExtractedTextEditor from './CVExtractedTextEditor';

type CVStatus = 'uploaded' | 'extracting' | 'extracted' | 'extraction_failed';

export interface CVMetadata {
  id: string;
  original_filename: string;
  media_type: string;
  size_bytes: number;
  sha256: string;
  status: CVStatus;
  created_at: string;
  extracted_at?: string;
  extracted_text?: string;
  extraction_error?: string;
}
export interface JobApplication {
  id: string;
  cv_document_id: string;
  target_role: string;
  job_description: string | null;
  interview_language: string;
  created_at: string;
  updated_at: string;
}

const UUID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function isValidUuid(value: unknown): value is string {
  return typeof value === 'string' && UUID_REGEX.test(value);
}

export function isCVMetadataResponse(value: unknown): value is CVMetadata {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return false;
  const obj = value as Record<string, unknown>;

  // Mandatory fields: id, original_filename, media_type, size_bytes, sha256, status, created_at
  if (!isValidUuid(obj.id)) return false;
  if (typeof obj.original_filename !== 'string' || obj.original_filename.trim() === '') return false;
  if (typeof obj.media_type !== 'string' || obj.media_type.trim() === '') return false;
  if (typeof obj.size_bytes !== 'number' || obj.size_bytes <= 0) return false;
  if (typeof obj.sha256 !== 'string' || obj.sha256.trim() === '') return false;

  const validStatuses = ['uploaded', 'extracting', 'extracted', 'extraction_failed'];
  if (typeof obj.status !== 'string' || !validStatuses.includes(obj.status)) return false;

  if (typeof obj.created_at !== 'string' || obj.created_at.trim() === '') return false;

  // Optional / nullable fields checked if present
  if (obj.extracted_at !== undefined && obj.extracted_at !== null && typeof obj.extracted_at !== 'string') return false;
  if (obj.extracted_text !== undefined && obj.extracted_text !== null && typeof obj.extracted_text !== 'string') return false;
  if (obj.extraction_error !== undefined && obj.extraction_error !== null && typeof obj.extraction_error !== 'string') return false;

  return true;
}

export function isJobApplicationResponse(value: unknown): value is JobApplication {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return false;
  const obj = value as Record<string, unknown>;
  if (!isValidUuid(obj.id)) return false;
  if (!isValidUuid(obj.cv_document_id)) return false;
  if (obj.target_role !== 'Backend Developer Intern') return false;
  if (obj.interview_language !== 'vi') return false;
  if (typeof obj.job_description !== 'string' && obj.job_description !== null) return false;
  if (typeof obj.created_at !== 'string' || obj.created_at.trim() === '') return false;
  if (typeof obj.updated_at !== 'string' || obj.updated_at.trim() === '') return false;
  return true;
}

export interface ResumePointer {
  version: 1;
  cv_document_id: string;
  job_application_id: string | null;
}

export function isResumePointer(value: unknown): value is ResumePointer {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return false;
  const obj = value as Record<string, unknown>;

  // Strictly accept only the three allowed keys: version, cv_document_id, job_application_id
  const keys = Object.keys(obj);
  if (keys.length !== 3) return false;
  if (!keys.includes('version') || !keys.includes('cv_document_id') || !keys.includes('job_application_id')) return false;

  if (obj.version !== 1) return false;
  if (!isValidUuid(obj.cv_document_id)) return false;
  if (obj.job_application_id !== null && !isValidUuid(obj.job_application_id)) return false;

  return true;
}

export const RESUME_POINTER_KEY = 'interview_resume_pointer';

export function getStoredPointer(): ResumePointer | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = sessionStorage.getItem(RESUME_POINTER_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as unknown;
    if (isResumePointer(parsed)) return parsed;
    sessionStorage.removeItem(RESUME_POINTER_KEY);
  } catch {
    try {
      sessionStorage.removeItem(RESUME_POINTER_KEY);
    } catch {
      // Storage may be unavailable; there is nothing else to restore safely.
    }
  }
  return null;
}

export function setStoredPointer(pointer: ResumePointer | null) {
  if (typeof window === 'undefined') return null;
  try {
    if (pointer) {
      sessionStorage.setItem(RESUME_POINTER_KEY, JSON.stringify(pointer));
    } else {
      sessionStorage.removeItem(RESUME_POINTER_KEY);
    }
  } catch {
    // ignore
  }
}

function clearLegacyItem(storage: Storage | null, key: string) {
  if (!storage) return;
  try {
    storage.removeItem(key);
  } catch {
    // ignore isolated storage error
  }
}

function clearAllLegacyStorage() {
  if (typeof window === 'undefined') return;

  let local: Storage | null = null;
  try {
    local = window.localStorage;
  } catch {
    // ignore
  }

  let session: Storage | null = null;
  try {
    session = window.sessionStorage;
  } catch {
    // ignore
  }

  clearLegacyItem(local, 'active_cv_metadata');
  clearLegacyItem(local, 'active_job_application');
  clearLegacyItem(session, 'active_cv_metadata');
  clearLegacyItem(session, 'active_job_application');
}

type CVUploadProps = {
  mode?: 'full' | 'prepare';
};

export default function CVUpload({ mode = 'full' }: CVUploadProps) {
  const [file, setFile] = useState<File | null>(null);
  const [metadata, setMetadata] = useState<CVMetadata | null>(null);
  const [status, setStatus] = useState<'idle' | 'uploading' | 'success' | 'error'>('idle');
  const [errorMessage, setErrorMessage] = useState<string>('');
  const [extractionUiError, setExtractionUiError] = useState<string>('');
  const [isExtracting, setIsExtracting] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Job Application States
  const [jobApp, setJobApp] = useState<JobApplication | null>(null);
  const [jobDescription, setJobDescription] = useState<string>('');
  const [isSubmittingJobApp, setIsSubmittingJobApp] = useState(false);
  const [jobAppError, setJobAppError] = useState<string>('');
  const [restoreTick, setRestoreTick] = useState(0);

  const MAX_SIZE = 5 * 1024 * 1024; // 5MB

  useEffect(() => {
    clearAllLegacyStorage();
    const pointer = getStoredPointer();
    if (!pointer) return;

    let isUnmounted = false;
    const abortController = new AbortController();
    const abortPendingRestore = () => {
      isUnmounted = true;
      abortController.abort();
    };
    window.addEventListener('pagehide', abortPendingRestore);

    const resetToSafeInitial = () => {
      setStoredPointer(null);
      if (!isUnmounted) {
        setMetadata(null);
        setStatus('idle');
        setJobApp(null);
        setJobDescription('');
      }
    };

    const restoreFromBackend = async () => {
      try {
        const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

        // 1. Fetch CV Metadata into local variable
        let fetchedCv: CVMetadata | null = null;
        const cvRes = await fetch(`${backendUrl}/api/v1/cv-documents/${pointer.cv_document_id}`, {
          signal: abortController.signal
        });
        const cvContentType = cvRes.headers.get('content-type');
        if (!cvRes.ok || !cvContentType || !cvContentType.includes('application/json')) {
          resetToSafeInitial();
          return;
        }
        const cvData = await cvRes.json() as unknown;
        if (!isCVMetadataResponse(cvData)) {
          resetToSafeInitial();
          return;
        }
        fetchedCv = cvData;

        // 2. Fetch JobApplication if present into local variable
        let fetchedApp: JobApplication | null = null;
        if (pointer.job_application_id) {
          const appRes = await fetch(`${backendUrl}/api/v1/job-applications/${pointer.job_application_id}`, {
            signal: abortController.signal
          });
          const appContentType = appRes.headers.get('content-type');
          if (!appRes.ok || !appContentType || !appContentType.includes('application/json')) {
            resetToSafeInitial();
            return;
          }
          const appData = await appRes.json() as unknown;
          if (!isJobApplicationResponse(appData)) {
            resetToSafeInitial();
            return;
          }

          // MUST verify JobApplication belongs to the CV in pointer
          if (appData.cv_document_id !== pointer.cv_document_id || appData.cv_document_id !== fetchedCv.id) {
            resetToSafeInitial();
            return;
          }

          fetchedApp = appData;
        }

        if (isUnmounted) return;

        // Atomic update to state: only update once all required data is verified
        if (pointer.job_application_id) {
          if (fetchedCv && fetchedApp) {
            setMetadata(fetchedCv);
            setStatus('success');
            setJobApp(fetchedApp);
            setJobDescription(fetchedApp.job_description || '');
          } else {
            resetToSafeInitial();
          }
        } else {
          if (fetchedCv) {
            setMetadata(fetchedCv);
            setStatus('success');
            setJobApp(null);
            setJobDescription('');
          } else {
            resetToSafeInitial();
          }
        }
      } catch (err: unknown) {
        if (err instanceof Error && err.name === 'AbortError') {
          return;
        }
        resetToSafeInitial();
      }
    };

    restoreFromBackend();

    return () => {
      window.removeEventListener('pagehide', abortPendingRestore);
      abortPendingRestore();
    };
  }, [restoreTick]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];
    if (!selected) {
      setFile(null);
      setStatus('idle');
      return;
    }

    if (selected.size > MAX_SIZE) {
      setErrorMessage('Dung lượng file vượt quá 5MB.');
      setStatus('error');
      setFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
      return;
    }

    const ext = selected.name.split('.').pop()?.toLowerCase();
    if (ext !== 'pdf' && ext !== 'docx') {
      setErrorMessage('Chỉ hỗ trợ định dạng PDF và DOCX.');
      setStatus('error');
      setFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
      return;
    }

    setFile(selected);
    setStatus('idle');
    setErrorMessage('');
    setExtractionUiError('');
    setMetadata(null);
    setJobApp(null);
    setJobDescription('');
    setJobAppError('');
    setStoredPointer(null);
    clearAllLegacyStorage();
  };

  const handleUpload = async () => {
    if (!file) return;

    setStatus('uploading');
    setErrorMessage('');
    setExtractionUiError('');
    setMetadata(null);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
      const res = await fetch(`${backendUrl}/api/v1/cv-documents`, {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        let errorMsg = 'Lỗi từ máy chủ khi tải lên file.';
        try {
          const errorData = await res.json();
          if (errorData?.detail) {
            errorMsg = typeof errorData.detail === 'string' 
              ? errorData.detail 
              : JSON.stringify(errorData.detail);
          }
        } catch {
          errorMsg = 'Lỗi từ máy chủ (không định dạng JSON).';
        }
        throw new Error(errorMsg);
      }

      const data: unknown = await res.json();
      if (!isCVMetadataResponse(data)) {
        throw new Error('Dữ liệu trả về không hợp lệ.');
      }
      setStatus('success');
      setMetadata(data);
      setStoredPointer({
        version: 1,
        cv_document_id: data.id,
        job_application_id: null
      });
    } catch (err: unknown) {
      setStatus('error');
      if (err instanceof Error) {
        setErrorMessage(err.message);
      } else {
        setErrorMessage('Lỗi không xác định.');
      }
    }
  };

  const handleExtract = async () => {
    if (!metadata) return;
    setIsExtracting(true);
    setExtractionUiError('');
    
    try {
      const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
      const res = await fetch(`${backendUrl}/api/v1/cv-documents/${metadata.id}/extract`, {
        method: 'POST',
      });

      if (!res.ok) {
        let errorMsg = 'Lỗi từ máy chủ khi trích xuất file.';
        try {
          const errorData = await res.json();
          if (errorData?.detail) {
            errorMsg = typeof errorData.detail === 'string' 
              ? errorData.detail 
              : JSON.stringify(errorData.detail);
          }
        } catch {
          errorMsg = 'Lỗi từ máy chủ (không định dạng JSON).';
        }
        throw new Error(errorMsg);
      }

      const data: unknown = await res.json();
      if (!isCVMetadataResponse(data)) {
        throw new Error('Dữ liệu trả về không hợp lệ.');
      }
      setMetadata(data);
      setStoredPointer({
        version: 1,
        cv_document_id: data.id,
        job_application_id: jobApp ? jobApp.id : null
      });
    } catch (err: unknown) {
      if (err instanceof Error) {
        setExtractionUiError(err.message);
      } else {
        setExtractionUiError('Lỗi không xác định.');
      }
    } finally {
      setIsExtracting(false);
    }
  };

  const handleCreateJobApp = async () => {
    if (!metadata || metadata.status !== 'extracted') return;
    setIsSubmittingJobApp(true);
    setJobAppError('');
    
    try {
      const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
      const res = await fetch(`${backendUrl}/api/v1/job-applications`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          cv_document_id: metadata.id,
          target_role: "Backend Developer Intern",
          job_description: jobDescription.trim() === '' ? null : jobDescription
        })
      });

      if (!res.ok) {
        let errorMsg = 'Lỗi từ máy chủ khi tạo hồ sơ.';
        try {
          const errorData = await res.json();
          if (errorData?.detail) {
            errorMsg = typeof errorData.detail === 'string' 
              ? errorData.detail 
              : JSON.stringify(errorData.detail);
          }
        } catch {
          errorMsg = 'Lỗi từ máy chủ (không định dạng JSON).';
        }
        throw new Error(errorMsg);
      }

      const data: unknown = await res.json();
      if (!isJobApplicationResponse(data)) {
        throw new Error('Dữ liệu trả về không hợp lệ.');
      }
      setJobApp(data);
      setStoredPointer({
        version: 1,
        cv_document_id: metadata.id,
        job_application_id: data.id
      });
    } catch (err: unknown) {
      if (err instanceof Error) {
        setJobAppError(err.message);
      } else {
        setJobAppError('Lỗi không xác định.');
      }
    } finally {
      setIsSubmittingJobApp(false);
    }
  };

  const handleUpdateJobApp = async () => {
    if (!jobApp || !metadata) return;
    setIsSubmittingJobApp(true);
    setJobAppError('');
    
    try {
      const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
      const res = await fetch(`${backendUrl}/api/v1/job-applications/${jobApp.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          job_description: jobDescription.trim() === '' ? null : jobDescription
        })
      });

      if (!res.ok) {
        let errorMsg = 'Lỗi từ máy chủ khi cập nhật hồ sơ.';
        try {
          const errorData = await res.json();
          if (errorData?.detail) {
            errorMsg = typeof errorData.detail === 'string' 
              ? errorData.detail 
              : JSON.stringify(errorData.detail);
          }
        } catch {
          errorMsg = 'Lỗi từ máy chủ (không định dạng JSON).';
        }
        throw new Error(errorMsg);
      }

      const data: unknown = await res.json();
      if (!isJobApplicationResponse(data)) {
        throw new Error('Dữ liệu trả về không hợp lệ.');
      }
      setJobApp(data);
      setStoredPointer({
        version: 1,
        cv_document_id: metadata.id,
        job_application_id: data.id
      });
    } catch (err: unknown) {
      if (err instanceof Error) {
        setJobAppError(err.message);
      } else {
        setJobAppError('Lỗi không xác định.');
      }
    } finally {
      setIsSubmittingJobApp(false);
    }
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB';
    return (bytes / 1024 / 1024).toFixed(2) + ' MB';
  };

  const handleResetNewApplication = () => {
    setStoredPointer(null);
    setFile(null);
    setMetadata(null);
    setStatus('idle');
    setErrorMessage('');
    setExtractionUiError('');
    setJobApp(null);
    setJobDescription('');
    setJobAppError('');
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  return (
    <div className="w-full max-w-3xl">
      <ApplicationSwitcher
        activeApplicationId={jobApp?.id || null}
        onSelectApplication={() => setRestoreTick((t) => t + 1)}
        onDeletedApplication={(deletedId) => {
          if (jobApp?.id === deletedId) {
            handleResetNewApplication();
          } else {
            setRestoreTick((t) => t + 1);
          }
        }}
        onCreateNew={metadata || jobApp ? handleResetNewApplication : undefined}
        compact
      />

      <section aria-labelledby="cv-upload-title">
        <div className="mb-5 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-xs font-semibold tracking-[0.12em] text-blue-700 uppercase">CV đầu vào</p>
            <h2 id="cv-upload-title" className="mt-1 text-2xl font-bold tracking-tight text-slate-950">Tải lên CV</h2>
          </div>
          <p className="text-xs leading-5 text-slate-500">PDF hoặc DOCX · Tối đa 5 MB</p>
        </div>

        <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50/80 p-5 sm:p-6">
          <label className="mb-3 block text-sm font-medium text-slate-700">Chọn file (PDF, DOCX - Tối đa 5MB)</label>
        <input 
          type="file" 
          accept=".pdf,.docx" 
          onChange={handleFileChange} 
          ref={fileInputRef}
          disabled={status === 'uploading' || isExtracting}
          className="block w-full text-sm text-slate-500
            file:mr-4 file:py-2.5 file:px-4
            file:rounded-lg file:border file:border-blue-200
            file:text-sm file:font-semibold
            file:bg-white file:text-blue-700
            hover:file:border-blue-300 hover:file:bg-blue-50 disabled:opacity-60"
        />

          {file && status !== 'error' && (
            <div className="mt-4 grid gap-2 border-t border-slate-200 pt-4 text-sm sm:grid-cols-[1fr_auto]">
              <p className="truncate font-medium text-slate-800">{file.name}</p>
              <p className="font-mono text-xs text-slate-500 tabular-nums">{formatSize(file.size)}</p>
            </div>
          )}

          <button 
            onClick={handleUpload}
            disabled={!file || status === 'uploading' || isExtracting}
            className="btn-primary-glow mt-5 inline-flex w-full items-center justify-center rounded-lg bg-blue-700 px-4 py-2.5 text-sm font-semibold text-white shadow-[0_10px_24px_-16px_rgba(29,78,216,0.9)] hover:bg-blue-800 focus-visible:ring-4 focus-visible:ring-blue-200 disabled:cursor-not-allowed disabled:bg-slate-300 disabled:shadow-none"
          >
            {status === 'uploading' && <span className="spinner-inline mr-2" aria-hidden="true" />}
            {status === 'uploading' ? 'Đang tải lên...' : 'Tải lên'}
          </button>
        </div>
      </section>

      {status === 'error' && (
        <div role="alert" className="panel-reveal mt-4 rounded-lg border-l-4 border-red-500 bg-red-50 p-4 text-sm text-red-800 break-words whitespace-pre-wrap">
          {errorMessage}
        </div>
      )}

      {status === 'success' && metadata && (
        <section className="panel-reveal mt-8 border-t border-slate-200 pt-7" aria-labelledby="uploaded-cv-title">
          <div className="flex items-start gap-3">
            <span className="mt-1 grid size-7 shrink-0 place-items-center rounded-md bg-emerald-100 text-sm font-bold text-emerald-700" aria-hidden="true">✓</span>
            <div className="min-w-0 flex-1">
              <p className="text-xs font-semibold tracking-[0.12em] text-emerald-700 uppercase">Đã nhận tệp</p>
              <h3 id="uploaded-cv-title" className="mt-1 text-lg font-semibold text-slate-950">Tải lên thành công!</h3>
              <dl className="mt-4 grid gap-x-6 gap-y-3 rounded-lg bg-slate-50 p-4 text-sm sm:grid-cols-2">
                <div>
                  <dt className="text-xs text-slate-500">Tên gốc</dt>
                  <dd className="mt-1 break-all font-medium text-slate-800">{metadata.original_filename}</dd>
                </div>
                <div>
                  <dt className="text-xs text-slate-500">Dung lượng</dt>
                  <dd className="mt-1 font-mono text-slate-800 tabular-nums">{formatSize(metadata.size_bytes)}</dd>
                </div>
                <div>
                  <dt className="text-xs text-slate-500">ID</dt>
                  <dd data-testid="cv-document-id" className="mt-1 break-all font-mono text-xs text-slate-700">{metadata.id}</dd>
                </div>
                <div>
                  <dt className="text-xs text-slate-500">Trạng thái</dt>
                  <dd data-testid="cv-document-status" className="mt-1 font-medium text-slate-800">{metadata.status}</dd>
                </div>
              </dl>
            </div>
          </div>

          <button
            onClick={handleExtract}
            disabled={isExtracting || metadata.status === 'extracted'}
            className={`mt-5 inline-flex w-full items-center justify-center rounded-lg px-4 py-2.5 text-sm font-semibold text-white ${
              isExtracting || metadata.status === 'extracted' 
                ? 'cursor-not-allowed bg-slate-300' 
                : 'btn-primary-glow bg-blue-700 hover:bg-blue-800 focus-visible:ring-4 focus-visible:ring-blue-200'
            }`}
          >
            {isExtracting && <span className="spinner-inline mr-2" aria-hidden="true" />}
            {isExtracting ? 'Đang trích xuất...' : 'Trích xuất nội dung CV'}
          </button>

          {extractionUiError && (
            <div role="alert" className="mt-4 rounded-lg border-l-4 border-red-500 bg-red-50 p-3 text-sm text-red-800 whitespace-pre-wrap">
              <strong>Lỗi hệ thống:</strong> {extractionUiError}
            </div>
          )}

          {metadata.status === 'extraction_failed' && (
            <div role="alert" className="mt-4 rounded-lg border-l-4 border-red-500 bg-red-50 p-3 text-sm text-red-800 whitespace-pre-wrap">
              <strong>Lỗi trích xuất:</strong> {metadata.extraction_error}
            </div>
          )}

          {metadata.status === 'extracted' && metadata.extracted_text && (
            <>
              <CVExtractedTextEditor
                key={metadata.id}
                cvId={metadata.id}
                extractedText={metadata.extracted_text}
                onUpdated={(updated) => setMetadata(updated)}
              />

              <section className="mt-8 border-t border-slate-200 pt-7" aria-labelledby="job-application-title">
                <div className="mb-5">
                  <p className="text-xs font-semibold tracking-[0.12em] text-blue-700 uppercase">Vị trí ứng tuyển</p>
                  <h3 id="job-application-title" className="mt-1 text-xl font-bold tracking-tight text-slate-950">Thông tin vị trí ứng tuyển</h3>
                  <p className="mt-2 text-sm leading-6 text-slate-600">JD là không bắt buộc, nhưng sẽ giúp câu hỏi sát với công việc bạn đang nhắm tới hơn.</p>
                </div>
                
                <div className="mb-4">
                  <label className="mb-2 block text-sm font-medium text-slate-700">Target role:</label>
                  <input
                    type="text"
                    readOnly
                    value="Backend Developer Intern"
                    className="w-full rounded-lg border border-slate-200 bg-slate-100 px-3 py-2.5 text-sm font-medium text-slate-700"
                  />
                </div>

                <div className="mb-4">
                  <label className="mb-2 block text-sm font-medium text-slate-700">
                    Job Description (Không bắt buộc. Bạn có thể để trống nếu chưa có JD.)
                  </label>
                  <textarea
                    value={jobDescription}
                    onChange={(e) => setJobDescription(e.target.value)}
                    disabled={isSubmittingJobApp}
                    maxLength={20000}
                    rows={4}
                    className="w-full rounded-lg border border-slate-300 bg-white px-3 py-3 text-sm leading-6 text-slate-800 placeholder:text-slate-400 focus:border-blue-600 focus:ring-4 focus:ring-blue-100 disabled:bg-slate-100"
                    placeholder="Dán Job Description vào đây..."
                  />
                  <div className="mt-1 text-right font-mono text-xs text-slate-500 tabular-nums">
                    {jobDescription.length} / 20000
                  </div>
                </div>

                {jobAppError && (
                  <div role="alert" className="mb-4 rounded-lg border-l-4 border-red-500 bg-red-50 p-3 text-sm text-red-800 whitespace-pre-wrap">
                    <strong>Lỗi:</strong> {jobAppError}
                  </div>
                )}

                {jobApp ? (
                  <div className="panel-reveal mb-4 rounded-xl border border-blue-200 bg-blue-50/70 p-4 text-sm text-blue-950">
                    <div className="flex items-center gap-2">
                      <span className="grid size-6 place-items-center rounded-md bg-blue-700 text-xs font-bold text-white" aria-hidden="true">✓</span>
                      <p className="font-semibold">Tạo hồ sơ thành công!</p>
                    </div>
                    <dl className="mt-3 grid gap-2 text-xs sm:grid-cols-2">
                      <div><dt className="text-blue-700">Application ID</dt><dd data-testid="job-application-id" className="mt-0.5 break-all font-mono">{jobApp.id}</dd></div>
                      <div><dt className="text-blue-700">Vị trí</dt><dd className="mt-0.5 font-medium">{jobApp.target_role}</dd></div>
                      <div><dt className="text-blue-700">Ngôn ngữ phỏng vấn</dt><dd className="mt-0.5">Tiếng Việt</dd></div>
                      <div><dt className="text-blue-700">Job Description</dt><dd data-testid="job-description-status" className="mt-0.5">{jobApp.job_description ? 'Đã cung cấp' : 'Không có'}</dd></div>
                    </dl>
                    
                    <button
                      onClick={handleUpdateJobApp}
                      disabled={isSubmittingJobApp}
                      className={`mt-4 inline-flex w-full items-center justify-center rounded-lg px-3 py-2 text-sm font-semibold text-white ${
                        isSubmittingJobApp ? 'cursor-not-allowed bg-slate-300' : 'btn-primary-glow bg-blue-700 hover:bg-blue-800 focus-visible:ring-4 focus-visible:ring-blue-200'
                      }`}
                    >
                      {isSubmittingJobApp && <span className="spinner-inline mr-2" aria-hidden="true" />}
                      {isSubmittingJobApp ? 'Đang cập nhật...' : 'Cập nhật Job Description'}
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={handleCreateJobApp}
                    disabled={isSubmittingJobApp}
                    className={`inline-flex w-full items-center justify-center rounded-lg px-4 py-2.5 text-sm font-semibold text-white ${
                      isSubmittingJobApp ? 'cursor-not-allowed bg-slate-300' : 'btn-primary-glow bg-blue-700 hover:bg-blue-800 focus-visible:ring-4 focus-visible:ring-blue-200'
                    }`}
                  >
                    {isSubmittingJobApp && <span className="spinner-inline mr-2" aria-hidden="true" />}
                    {isSubmittingJobApp ? 'Đang xử lý...' : 'Tạo hồ sơ ứng tuyển'}
                  </button>
                )}

                {jobApp && (mode === 'full' ? (
                  <AIAnalysis 
                    applicationId={jobApp.id} 
                    cvDocument={metadata} 
                    jobDescription={jobApp.job_description || undefined} 
                  />
                ) : (
                  <div className="mt-6 border-t border-slate-200 pt-6">
                    <p className="text-sm leading-6 text-slate-600">Hồ sơ đã sẵn sàng. Bước tiếp theo là xem phân tích để chuẩn bị câu hỏi phỏng vấn.</p>
                    <Link href="/analysis" className="mt-4 inline-flex rounded-lg bg-blue-700 px-5 py-2.5 text-sm font-semibold text-white hover:bg-blue-800">
                      Tiếp tục phân tích hồ sơ
                    </Link>
                  </div>
                ))}
              </section>
            </>
          )}
        </section>
      )}
    </div>
  );
}
