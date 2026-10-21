'use client';

import { useRouter } from 'next/navigation';
import AppFrame from '../components/AppFrame';
import InterviewHistory from '../components/InterviewHistory';
import ResumeWorkspace from '../components/ResumeWorkspace';

export default function PracticeSetupPage() {
  const router = useRouter();

  return (
    <AppFrame current="practice">
      <main id="main-content" className="app-container py-9 sm:py-14">
        <section className="enter-up mx-auto max-w-5xl">
          <div className="mb-8 max-w-2xl">
            <p className="text-xs font-bold tracking-[0.13em] text-blue-700 uppercase">Trước buổi luyện</p>
            <h1 className="mt-3 text-3xl font-bold tracking-[-0.04em] text-slate-950 sm:text-4xl">Chọn nội dung luyện tập</h1>
            <p className="mt-3 text-base leading-7 text-slate-600">
              Chọn một cách luyện phù hợp. Sau khi tạo bộ câu hỏi, bạn sẽ sang trang Phỏng vấn để làm bài.
            </p>
          </div>
          <section className="surface-panel rounded-[1.45rem] p-4 sm:p-8">
            <ResumeWorkspace>
              {({ application }) => (
                <InterviewHistory
                  key={application.id}
                  applicationId={application.id}
                  selectedSessionId={null}
                  onSelectSession={() => router.push('/interview')}
                  onAttemptCreated={() => router.push('/interview')}
                  viewMode="setup"
                />
              )}
            </ResumeWorkspace>
          </section>
        </section>
      </main>
    </AppFrame>
  );
}
