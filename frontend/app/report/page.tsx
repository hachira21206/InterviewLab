'use client';

import { Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import AppFrame from '../components/AppFrame';
import InterviewQuestions from '../components/InterviewQuestions';
import ResumeWorkspace from '../components/ResumeWorkspace';

function ReportContent() {
  const searchParams = useSearchParams();
  const selectedSessionId = searchParams.get('sessionId');

  return (
    <ResumeWorkspace>
      {({ application }) => <InterviewQuestions key={`${application.id}:${selectedSessionId ?? 'latest'}`} applicationId={application.id} analysisCompleted mode="report" selectedSessionId={selectedSessionId} />}
    </ResumeWorkspace>
  );
}

export default function ReportPage() {
  return (
    <AppFrame current="report">
      <main id="main-content" className="app-container py-9 sm:py-14">
        <section className="enter-up mx-auto max-w-5xl">
          <div className="mb-8 max-w-2xl">
            <p className="text-xs font-bold tracking-[0.13em] text-blue-700 uppercase">Bước 06 · Đánh giá</p>
            <h1 className="mt-3 text-3xl font-bold tracking-[-0.04em] text-slate-950 sm:text-4xl">Báo cáo buổi phỏng vấn</h1>
            <p className="mt-3 text-base leading-7 text-slate-600">
              Xem điểm và nhận xét theo từng câu. Nếu chưa có báo cáo, bạn có thể đồng ý gửi bài làm để AI đánh giá tại đây.
            </p>
          </div>
          <section className="surface-panel rounded-[1.45rem] p-4 sm:p-8">
            <Suspense fallback={<p className="text-sm text-slate-600">Đang mở báo cáo...</p>}>
              <ReportContent />
            </Suspense>
          </section>
        </section>
      </main>
    </AppFrame>
  );
}
