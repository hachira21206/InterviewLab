'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import AppFrame from '../components/AppFrame';
import InterviewHistory from '../components/InterviewHistory';
import InterviewProgressDashboard from '../components/InterviewProgressDashboard';
import ResumeWorkspace from '../components/ResumeWorkspace';

export default function ProgressPage() {
  const router = useRouter();
  return (
    <AppFrame current="progress">
      <main id="main-content" className="app-container py-9 sm:py-14">
        <section className="enter-up mx-auto max-w-5xl">
          <div className="mb-8 max-w-2xl">
            <p className="text-xs font-bold tracking-[0.13em] text-blue-700 uppercase">Bước 07 · Theo dõi</p>
            <h1 className="mt-3 text-3xl font-bold tracking-[-0.04em] text-slate-950 sm:text-4xl">Tiến bộ qua từng lần luyện</h1>
            <p className="mt-3 text-base leading-7 text-slate-600">So sánh điểm số và nhìn ra nhóm kỹ năng đang tiến bộ qua các lần phỏng vấn.</p>
          </div>
          <section className="surface-panel rounded-[1.45rem] p-4 sm:p-8">
            <ResumeWorkspace>
              {({ application }) => (
                <>
                  <InterviewProgressDashboard applicationId={application.id} />
                  <div className="mt-10">
                    <InterviewHistory
                      key={application.id}
                      applicationId={application.id}
                      selectedSessionId={null}
                      onSelectSession={(sessionId) => router.push(`/result?sessionId=${sessionId}`)}
                      onAttemptCreated={() => router.push('/interview')}
                      viewMode="results"
                    />
                  </div>
                </>
              )}
            </ResumeWorkspace>
            <div className="mt-8 flex flex-wrap justify-end gap-3 border-t border-slate-200 pt-6">
              <Link href="/practice" className="rounded-lg bg-blue-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-800">Chọn bài luyện mới →</Link>
            </div>
          </section>
        </section>
      </main>
    </AppFrame>
  );
}
