'use client';
import Link from 'next/link';
import { useState, useEffect, useRef } from 'react';
import { CVMetadata } from './CVUpload';
import InterviewQuestions from './InterviewQuestions';

interface TechnicalSkill { name: string; level: 'mentioned' | 'demonstrated' | 'unclear'; evidence: string; }
interface ProjectInfo { name: string; description: string; technologies: string[]; evidence: string; }
interface EducationInfo { institution: string; major: string; status: string; }
interface SectionEvidence { title: string; evidence: string; }
interface GapInfo { title: string; reason: string; }
interface RequirementMatch { requirement: string; evidence: string; }
interface InterviewTopic { topic: string; reason: string; priority: 'high' | 'medium' | 'low'; }

export interface CandidateAnalysis {
  summary_vi: string;
  candidate_level: 'beginner' | 'junior_ready' | 'unclear';
  technical_skills: TechnicalSkill[];
  projects: ProjectInfo[];
  education: EducationInfo[];
  strengths: SectionEvidence[];
  gaps: GapInfo[];
  matched_requirements: RequirementMatch[];
  missing_requirements: RequirementMatch[];
  recommended_interview_topics: InterviewTopic[];
  language_detected: 'vi' | 'en' | 'unknown';
  warnings: string[];
}

export interface ApplicationAnalysisResponse {
  id: string;
  job_application_id: string;
  status: 'pending' | 'analyzing' | 'completed' | 'failed';
  provider: string;
  model: string;
  schema_version: string;
  prompt_version: string;
  analysis_data?: CandidateAnalysis;
  error_code?: string;
  error_message?: string;
}

export function isCandidateAnalysis(data: unknown): data is CandidateAnalysis {
  if (!data || typeof data !== 'object') return false;
  const d = data as Record<string, unknown>;
  if (typeof d.summary_vi !== 'string') return false;
  if (!['beginner', 'junior_ready', 'unclear'].includes(d.candidate_level as string)) return false;
  if (!['vi', 'en', 'unknown'].includes(d.language_detected as string)) return false;
  if (!Array.isArray(d.warnings) || !d.warnings.every(x => typeof x === 'string')) return false;

  const isArrayOf = (arr: unknown, checker: (val: Record<string, unknown>) => boolean) => 
    Array.isArray(arr) && arr.every(x => x && typeof x === 'object' && checker(x as Record<string, unknown>));

  if (!isArrayOf(d.technical_skills, x => typeof x.name === 'string' && ['mentioned', 'demonstrated', 'unclear'].includes(x.level as string) && typeof x.evidence === 'string')) return false;
  if (!isArrayOf(d.projects, x => typeof x.name === 'string' && typeof x.description === 'string' && Array.isArray(x.technologies) && typeof x.evidence === 'string')) return false;
  if (!isArrayOf(d.education, x => typeof x.institution === 'string' && typeof x.major === 'string' && typeof x.status === 'string')) return false;
  if (!isArrayOf(d.strengths, x => typeof x.title === 'string' && typeof x.evidence === 'string')) return false;
  if (!isArrayOf(d.gaps, x => typeof x.title === 'string' && typeof x.reason === 'string')) return false;
  if (!isArrayOf(d.matched_requirements, x => typeof x.requirement === 'string' && typeof x.evidence === 'string')) return false;
  if (!Array.isArray(d.missing_requirements) || !d.missing_requirements.every(x => typeof x === 'string' || (x && typeof x === 'object' && typeof (x as Record<string, unknown>).requirement === 'string'))) return false;
  if (!isArrayOf(d.recommended_interview_topics, x => typeof x.topic === 'string' && typeof x.reason === 'string' && ['high', 'medium', 'low'].includes(x.priority as string))) return false;

  return true;
}

export function isAnalysisResponse(data: unknown): data is ApplicationAnalysisResponse {
  if (!data || typeof data !== 'object') return false;
  const d = data as Record<string, unknown>;
  
  if (typeof d.id !== 'string' || typeof d.job_application_id !== 'string') return false;
  if (!['pending', 'analyzing', 'completed', 'failed'].includes(d.status as string)) return false;
  if (typeof d.provider !== 'string' || typeof d.model !== 'string') return false;

  if (d.status === 'completed' && !isCandidateAnalysis(d.analysis_data)) return false;
  if (d.status === 'failed' && (typeof d.error_code !== 'string' || typeof d.error_message !== 'string')) return false;

  return true;
}

function isErrorResponse(data: unknown): data is { detail: string } {
  if (!data || typeof data !== 'object') return false;
  const d = data as Record<string, unknown>;
  return typeof d.detail === 'string';
}

interface AIAnalysisProps {
  applicationId: string;
  cvDocument: CVMetadata;
  jobDescription?: string;
  showInterviewQuestions?: boolean;
}

export default function AIAnalysis({ applicationId, cvDocument, jobDescription, showInterviewQuestions = true }: AIAnalysisProps) {
  const [analysis, setAnalysis] = useState<CandidateAnalysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [consent, setConsent] = useState(false);
  const [status, setStatus] = useState<string>('pending');
  const [providerName, setProviderName] = useState<string>('Groq Free API');
  
  const abortControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    const abortController = new AbortController();
    
    const fetchAnalysis = async () => {
      try {
        const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://127.0.0.1:8000';
        const res = await fetch(`${backendUrl}/api/v1/job-applications/${applicationId}/analysis`, {
          signal: abortController.signal
        });
        
        const contentType = res.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
           throw new Error('Server trả về dữ liệu không hợp lệ (Không phải JSON).');
        }
        
        const data = await res.json();
        
        if (res.ok) {
          if (isAnalysisResponse(data)) {
            if (data.status === 'failed') {
               setError(data.error_message || 'Phân tích thất bại.');
            } else if (data.status === 'completed') {
               if (data.analysis_data) setAnalysis(data.analysis_data);
            }
            setStatus(data.status);
            if (data.provider) setProviderName(data.provider);
          } else {
            setError('Dữ liệu trả về không hợp lệ');
          }
        } else if (res.status !== 404) {
          if (!abortController.signal.aborted) {
              if (isErrorResponse(data)) setError(data.detail);
              else setError('Lỗi khi tải kết quả phân tích.');
          }
        }
      } catch (err: unknown) {
        if (err instanceof Error && err.name !== 'AbortError') {
          setError('Lỗi kết nối khi tải kết quả phân tích.');
        }
      }
    };

    fetchAnalysis();
    return () => abortController.abort();
  }, [applicationId]);

  useEffect(() => {
    return () => {
      if (abortControllerRef.current) abortControllerRef.current.abort();
    };
  }, []);

  const handleAnalyze = async () => {
    setLoading(true);
    setError(null);
    
    if (abortControllerRef.current) abortControllerRef.current.abort();
    
    const abortController = new AbortController();
    abortControllerRef.current = abortController;
    
    try {
      const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://127.0.0.1:8000';
      const res = await fetch(`${backendUrl}/api/v1/job-applications/${applicationId}/analysis`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ consent_to_external_ai: consent }),
        signal: abortController.signal
      });
      
      const contentType = res.headers.get('content-type');
      if (!contentType || !contentType.includes('application/json')) {
         throw new Error('Server trả về dữ liệu không hợp lệ (Không phải JSON).');
      }
      
      const data = await res.json();
      
      if (!res.ok) {
        if (isErrorResponse(data)) setError(data.detail);
        else setError('Lỗi hệ thống. Vui lòng thử lại sau.');
      } else {
        if (isAnalysisResponse(data)) {
          if (data.status === 'failed') {
            setError(data.error_message || data.error_code || 'Phân tích thất bại.');
          } else if (data.status === 'completed' && data.analysis_data) {
            setAnalysis(data.analysis_data);
          }
          setStatus(data.status);
          if (data.provider) setProviderName(data.provider);
        } else {
          setError('Dữ liệu trả về không hợp lệ');
        }
      }
    } catch (err: unknown) {
      if (err instanceof Error && err.name !== 'AbortError') {
        setError(err.message || 'Lỗi kết nối đến máy chủ.');
      } else if (!(err instanceof Error)) {
        setError('Lỗi kết nối đến máy chủ.');
      }
    } finally {
      if (!abortController.signal.aborted) {
         setLoading(false);
      }
    }
  };

  const cvChars = cvDocument.extracted_text ? cvDocument.extracted_text.length : 0;
  const jdChars = jobDescription ? jobDescription.length : 0;

  return (
    <section className="mt-9 border-t border-slate-200 pt-8" aria-labelledby="analysis-title">
      <div className="mb-6">
        <p className="text-xs font-semibold tracking-[0.12em] text-blue-700 uppercase">03 · Phân tích hồ sơ</p>
        <h2 id="analysis-title" className="mt-1 text-2xl font-bold tracking-tight text-slate-950">Phân tích CV và vị trí ứng tuyển</h2>
        <p className="mt-2 text-sm leading-6 text-slate-600">Xác định điểm mạnh, khoảng trống kiến thức và trọng tâm nên luyện trước buổi phỏng vấn.</p>
      </div>
      
      {status === 'completed' && analysis ? (
        <div className="space-y-7">
          <div className="rounded-xl border-l-4 border-blue-600 bg-blue-50/70 p-5">
            <h3 className="mb-2 font-semibold text-blue-950">Tóm tắt</h3>
            <p className="text-sm leading-6 text-blue-900 whitespace-pre-wrap">{analysis.summary_vi}</p>
          </div>
          
          <div className="flex flex-col gap-2 border-b border-slate-200 pb-6 sm:flex-row sm:items-center sm:justify-between">
            <h3 className="text-sm font-medium text-slate-600">Đánh giá cấp độ</h3>
            <span className="text-base font-semibold text-blue-700">{
              analysis.candidate_level === 'beginner' ? 'Người mới bắt đầu' :
              analysis.candidate_level === 'junior_ready' ? 'Sẵn sàng làm Junior' : 'Chưa rõ ràng'
            }</span>
          </div>

          <div>
            <h3 className="mb-3 font-semibold text-slate-900">Kỹ năng chuyên môn</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {analysis.technical_skills?.map((skill, idx) => (
                <article key={idx} className="rounded-lg bg-slate-50 p-4">
                  <div className="flex items-start justify-between gap-3 font-semibold text-slate-800">
                    {skill.name}
                    <span className="shrink-0 rounded-md border border-slate-200 bg-white px-2 py-1 text-xs font-medium text-slate-600">
                      {skill.level}
                    </span>
                  </div>
                  <p className="mt-2 text-sm leading-6 text-slate-600">{skill.evidence}</p>
                </article>
              ))}
            </div>
          </div>

          <div className="grid gap-6 md:grid-cols-2">
            <section>
              <div className="mb-3 flex items-center justify-between">
                <h3 className="font-semibold text-emerald-800">Điểm mạnh</h3>
                <span className="rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-semibold text-emerald-800">
                  {analysis.strengths?.length || 0}
                </span>
              </div>
              {analysis.strengths && analysis.strengths.length > 0 ? (
                <ul className="space-y-2">
                  {analysis.strengths.map((s, idx) => (
                    <li key={idx} className="rounded-lg border-l-2 border-emerald-500 bg-emerald-50/70 p-3 text-sm leading-6 text-emerald-950">
                      <strong className="mb-1 block">{s.title}</strong>
                      {s.evidence}
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="rounded-lg border border-dashed border-emerald-200 bg-emerald-50/40 p-4 text-xs leading-5 text-emerald-800">
                  Chưa ghi nhận điểm mạnh nổi bật trong hồ sơ.
                </div>
              )}
            </section>

            <section>
              <div className="mb-3 flex items-center justify-between">
                <h3 className="font-semibold text-amber-800">Khoảng trống kiến thức (Gaps)</h3>
                <span className="rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-semibold text-amber-800">
                  {analysis.gaps?.length || 0}
                </span>
              </div>
              {analysis.gaps && analysis.gaps.length > 0 ? (
                <ul className="space-y-2">
                  {analysis.gaps.map((g, idx) => (
                    <li key={idx} className="rounded-lg border-l-2 border-amber-500 bg-amber-50/70 p-3 text-sm leading-6 text-amber-950">
                      <strong className="mb-1 block">{g.title}</strong>
                      {g.reason}
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="rounded-lg border border-dashed border-amber-300 bg-amber-50/60 p-4 text-xs leading-5 text-amber-900">
                  <p className="font-semibold">Chưa ghi nhận khoảng trống kiến thức lớn</p>
                  <p className="mt-1 text-slate-600">
                    Ứng viên đã đáp ứng tốt các tiêu chí cơ bản của vị trí. Bạn có thể dán thêm Job Description (JD) chi tiết của nhà tuyển dụng để AI đối chiếu các yêu cầu công nghệ chuyên sâu hơn.
                  </p>
                </div>
              )}
            </section>
          </div>

          <div>
            <h3 className="mb-3 font-semibold text-slate-900">Đề xuất phỏng vấn</h3>
            <div className="space-y-3">
              {analysis.recommended_interview_topics?.map((topic, idx) => (
                <article key={idx} className="rounded-lg border border-slate-200 bg-white p-4">
                  <div className="flex items-start justify-between gap-3">
                    <strong className="text-sm text-slate-900">{topic.topic}</strong>
                    <span className="ml-2 shrink-0 rounded-md bg-blue-50 px-2 py-1 text-xs font-medium text-blue-700">{topic.priority}</span>
                  </div>
                  <p className="mt-2 text-sm leading-6 text-slate-600">{topic.reason}</p>
                </article>
              ))}
            </div>
          </div>
          
          <div className="text-right text-xs text-slate-400">Provider: {providerName}</div>
          {!showInterviewQuestions && (
            <div className="flex flex-wrap items-center justify-between gap-4 border-t border-slate-200 pt-6">
              <p className="text-sm text-slate-600">Bạn đã có đủ ngữ cảnh để tạo bộ câu hỏi phỏng vấn.</p>
              <Link href="/interview" className="rounded-lg bg-blue-700 px-5 py-2.5 text-sm font-semibold text-white hover:bg-blue-800">
                Sang phần phỏng vấn
              </Link>
            </div>
          )}
        </div>
      ) : (
        <div className="rounded-xl bg-slate-50 p-5 sm:p-6">
          <div className="grid gap-5 sm:grid-cols-[1fr_auto] sm:items-start">
            <div className="text-sm leading-6 text-slate-600">
              <p><strong className="font-semibold text-slate-800">Provider:</strong> {providerName}</p>
              <p className="mt-2 max-w-xl">Nội dung CV và Job Description sẽ được gửi đến nhà cung cấp AI bên ngoài để thực hiện phân tích.</p>
            </div>
            <dl className="grid grid-cols-2 gap-3 text-xs">
              <div className="rounded-lg border border-slate-200 bg-white px-3 py-2">
                <dt className="text-slate-500">CV</dt>
                <dd className={`mt-1 font-mono font-semibold tabular-nums ${cvChars > 8000 ? "text-red-700" : "text-slate-800"}`}>{cvChars.toLocaleString()} / 8,000</dd>
              </div>
              <div className="rounded-lg border border-slate-200 bg-white px-3 py-2">
                <dt className="text-slate-500">JD</dt>
                <dd className={`mt-1 font-mono font-semibold tabular-nums ${jdChars > 4000 ? "text-red-700" : "text-slate-800"}`}>{jdChars.toLocaleString()} / 4,000</dd>
              </div>
            </dl>
          </div>

          <label className="mt-6 flex cursor-pointer items-start gap-3 border-t border-slate-200 pt-5 group">
            <div className="flex h-5 items-center">
              <input
                type="checkbox"
                checked={consent}
                onChange={(e) => setConsent(e.target.checked)}
                disabled={loading || status === 'analyzing'}
                className="size-4 rounded border border-slate-300 bg-white text-blue-700 focus:ring-4 focus:ring-blue-200 disabled:opacity-50"
              />
            </div>
            <span className="text-sm leading-6 text-slate-700 group-hover:text-slate-950">
              Tôi đồng ý gửi nội dung CV và Job Description đến nhà cung cấp AI bên ngoài để thực hiện phân tích.
            </span>
          </label>

          {error && (
            <div role="alert" className="mt-4 rounded-lg border-l-4 border-red-500 bg-red-50 p-3 text-sm text-red-800">
              {error}
            </div>
          )}

          <button
            onClick={handleAnalyze}
            disabled={!consent || loading || status === 'analyzing'}
            className="btn-primary-glow mt-5 inline-flex w-full items-center justify-center rounded-lg bg-blue-700 px-6 py-2.5 text-sm font-semibold text-white hover:bg-blue-800 focus-visible:ring-4 focus-visible:ring-blue-200 disabled:cursor-not-allowed disabled:bg-slate-300 sm:w-auto"
          >
            {(loading || status === 'analyzing') && (
              <span className="spinner-inline mr-2" aria-hidden="true" />
            )}
            {loading || status === 'analyzing' ? 'Đang phân tích...' : status === 'failed' ? 'Thử lại' : 'Phân tích hồ sơ'}
          </button>
        </div>
      )}
      {showInterviewQuestions && <InterviewQuestions applicationId={applicationId} analysisCompleted={status === 'completed'} />}
    </section>
  );
}
