'use client';

import AppFrame from '../components/AppFrame';
import InterviewQuestions from '../components/InterviewQuestions';
import ResumeWorkspace from '../components/ResumeWorkspace';

export default function InterviewPage() {
  return (
    <AppFrame current="interview">
      <main id="main-content" className="app-container py-9 sm:py-14">
        <section className="enter-up mx-auto max-w-5xl">
          <div className="mb-8 max-w-2xl">
            <p className="text-xs font-bold tracking-[0.13em] text-blue-700 uppercase">Bước 03 · Luyện trả lời</p>
            <h1 className="mt-3 text-3xl font-bold tracking-[-0.04em] text-slate-950 sm:text-4xl">Tập trung vào từng câu hỏi</h1>
            <p className="mt-3 text-base leading-7 text-slate-600">Trả lời theo cách của bạn. Bạn có thể bỏ qua câu hỏi và quay lại xem toàn bộ transcript khi hoàn thành.</p>
          </div>
          <section className="surface-panel rounded-[1.45rem] p-4 sm:p-8">
            <ResumeWorkspace>
              {({ application }) => <InterviewQuestions applicationId={application.id} analysisCompleted mode="interview" />}
            </ResumeWorkspace>
          </section>
        </section>
      </main>
    </AppFrame>
  );
}
