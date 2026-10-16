'use client';

import AppFrame from '../components/AppFrame';
import InterviewQuestions from '../components/InterviewQuestions';
import ResumeWorkspace from '../components/ResumeWorkspace';

export default function ResultPage() {
  return (
    <AppFrame current="result">
      <main id="main-content" className="app-container py-9 sm:py-14">
        <section className="enter-up mx-auto max-w-5xl">
          <div className="mb-8 max-w-2xl">
            <p className="text-xs font-bold tracking-[0.13em] text-blue-700 uppercase">Bước 04 · Nhìn lại</p>
            <h1 className="mt-3 text-3xl font-bold tracking-[-0.04em] text-slate-950 sm:text-4xl">Kết quả buổi phỏng vấn</h1>
            <p className="mt-3 text-base leading-7 text-slate-600">Xem transcript, đánh giá và những điểm nên cải thiện trong lần luyện tiếp theo.</p>
          </div>
          <section className="surface-panel rounded-[1.45rem] p-4 sm:p-8">
            <ResumeWorkspace>
              {({ application }) => <InterviewQuestions applicationId={application.id} analysisCompleted mode="result" />}
            </ResumeWorkspace>
          </section>
        </section>
      </main>
    </AppFrame>
  );
}
