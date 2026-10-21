'use client';

import Link from 'next/link';
import { useEffect, useState, type ReactNode } from 'react';
import {
  getStoredPointer,
  setStoredPointer,
  isCVMetadataResponse,
  isJobApplicationResponse,
  type CVMetadata,
  type JobApplication,
} from './CVUpload';
import ApplicationSwitcher, { type ApplicationListItem } from './ApplicationSwitcher';

type ResumeWorkspaceProps = {
  children: (data: { cvDocument: CVMetadata; application: JobApplication }) => ReactNode;
};

export default function ResumeWorkspace({ children }: ResumeWorkspaceProps) {
  const [data, setData] = useState<{ cvDocument: CVMetadata; application: JobApplication } | null>(null);
  const [message, setMessage] = useState('Đang mở hồ sơ của bạn...');
  const [isLoading, setIsLoading] = useState(true);
  const [reloadTick, setReloadTick] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    const load = async () => {
      await Promise.resolve();
      const pointer = getStoredPointer();
      if (!pointer?.job_application_id) {
        if (!controller.signal.aborted) {
          setData(null);
          setMessage('Bạn có thể chọn một hồ sơ đã tạo bên dưới hoặc tải CV mới.');
          setIsLoading(false);
        }
        return;
      }

      try {
        let backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
        if (backendUrl.endsWith('/')) backendUrl = backendUrl.slice(0, -1);

        const [cvResponse, appResponse] = await Promise.all([
          fetch(`${backendUrl}/api/v1/cv-documents/${pointer.cv_document_id}`, { signal: controller.signal }),
          fetch(`${backendUrl}/api/v1/job-applications/${pointer.job_application_id}`, { signal: controller.signal }),
        ]);

        const cvContentType = cvResponse.headers.get('content-type');
        const appContentType = appResponse.headers.get('content-type');
        if (!cvResponse.ok || !appResponse.ok || !cvContentType?.includes('application/json') || !appContentType?.includes('application/json')) {
          throw new Error('Hồ sơ không còn khả dụng.');
        }

        const [cvValue, appValue] = await Promise.all([cvResponse.json() as Promise<unknown>, appResponse.json() as Promise<unknown>]);
        if (!isCVMetadataResponse(cvValue) || !isJobApplicationResponse(appValue) || appValue.cv_document_id !== cvValue.id || appValue.cv_document_id !== pointer.cv_document_id) {
          throw new Error('Không thể xác minh hồ sơ.');
        }

        if (!controller.signal.aborted) {
          setData({ cvDocument: cvValue, application: appValue });
          setIsLoading(false);
        }
      } catch (error: unknown) {
        if (!controller.signal.aborted) {
          setStoredPointer(null);
          setData(null);
          setMessage(error instanceof Error ? error.message : 'Không thể mở hồ sơ.');
          setIsLoading(false);
        }
      }
    };

    load();
    return () => controller.abort();
  }, [reloadTick]);

  const handleSelectApplication = (item: ApplicationListItem) => {
    setData(null);
    setMessage('Đang mở hồ sơ của bạn...');
    setIsLoading(true);
    setStoredPointer({
      version: 1,
      cv_document_id: item.cv_document_id,
      job_application_id: item.id,
    });
    setReloadTick((t) => t + 1);
  };

  if (data) {
    return (
      <>
        <ApplicationSwitcher
          activeApplicationId={data.application.id}
          onSelectApplication={handleSelectApplication}
          compact
        />
        {children(data)}
      </>
    );
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <ApplicationSwitcher
        activeApplicationId={null}
        onSelectApplication={handleSelectApplication}
      />
      <section className="surface-panel rounded-2xl p-6 text-center sm:p-8" aria-live="polite" aria-busy={isLoading}>
        <span className="mx-auto grid size-11 place-items-center rounded-2xl bg-blue-50 text-sm font-semibold text-blue-700" aria-hidden="true">CV</span>
        <h2 className="mt-4 text-xl font-bold tracking-tight text-slate-950">{isLoading ? 'Đang mở hồ sơ' : 'Chưa có hồ sơ đang mở'}</h2>
        <p className="mt-2 text-sm leading-6 text-slate-600">{message}</p>
        {!isLoading && (
          <Link href="/prepare" className="mt-6 inline-flex rounded-lg bg-blue-700 px-5 py-2.5 text-sm font-semibold text-white hover:bg-blue-800">
            Đi tới chuẩn bị hồ sơ mới
          </Link>
        )}
      </section>
    </div>
  );
}
