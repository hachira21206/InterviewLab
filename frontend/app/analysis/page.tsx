'use client';

import AppFrame from '../components/AppFrame';
import AIAnalysis from '../components/AIAnalysis';
import ResumeWorkspace from '../components/ResumeWorkspace';

export default function AnalysisPage() {
  return (
    <AppFrame current="analysis">
      <main id="main-content" className="app-container py-9 sm:py-14">
        <section className="enter-up mx-auto max-w-5xl">
          <div className="mb-8 max-w-2xl">
            <p className="text-xs font-bold tracking-[0.13em] text-blue-700 uppercase">Bước 02 · Hiểu hồ sơ</p>
            <h1 className="mt-3 text-3xl font-bold tracking-[-0.04em] text-slate-950 sm:text-4xl">Phân tích điểm mạnh trước khi luyện</h1>
            <p className="mt-3 text-base leading-7 text-slate-600">Xem CV của bạn phù hợp với vị trí ở đâu và chọn những chủ đề nên tập trung trước.</p>
          </div>
          <section className="surface-panel rounded-[1.45rem] p-4 sm:p-8">
            <ResumeWorkspace>
              {({ cvDocument, application }) => (
                <AIAnalysis applicationId={application.id} cvDocument={cvDocument} jobDescription={application.job_description || undefined} showInterviewQuestions={false} />
              )}
            </ResumeWorkspace>
          </section>
        </section>
      </main>
    </AppFrame>
  );
}
