import Link from 'next/link';
import AppFrame from './components/AppFrame';

const journey = [
  {
    number: '01',
    title: 'Chuẩn bị hồ sơ',
    detail: 'Tải CV, kiểm tra nội dung và thêm mô tả công việc nếu có.',
  },
  {
    number: '02',
    title: 'Phân tích hồ sơ',
    detail: 'Xem điểm mạnh và chủ đề nên ôn trước khi bắt đầu.',
  },
  {
    number: '03',
    title: 'Chọn bài luyện',
    detail: 'Chọn phỏng vấn tổng hợp, một chuyên đề hoặc luyện bù điểm yếu.',
  },
  {
    number: '04',
    title: 'Làm và nộp bài',
    detail: 'Trả lời 10 câu lần lượt; xác nhận nộp ở câu cuối.',
  },
  {
    number: '05',
    title: 'Xem kết quả',
    detail: 'Đọc lại câu trả lời và những câu đã bỏ qua.',
  },
  {
    number: '06',
    title: 'Xem báo cáo',
    detail: 'Nhận điểm và góp ý từ AI khi bạn đồng ý chia sẻ bài làm.',
  },
  {
    number: '07',
    title: 'Theo dõi tiến bộ',
    detail: 'So sánh các lần luyện, rồi chọn bài mới nếu muốn luyện tiếp.',
  },
];

export default function Home() {
  return (
    <AppFrame current="home">
      <main id="main-content" className="app-container py-10 sm:py-16">
        <section className="enter-up grid gap-10 lg:grid-cols-[minmax(0,1fr)_20rem] lg:items-end">
          <div className="max-w-3xl">
            <p className="mb-4 flex items-center gap-2 text-sm font-semibold text-blue-700">
              <span className="h-px w-7 bg-blue-500" aria-hidden="true" />
              Không gian luyện tập cá nhân
            </p>
            <h1 className="text-4xl leading-[1.04] font-bold tracking-[-0.045em] text-balance text-slate-950 sm:text-5xl lg:text-[3.6rem]">
              Luyện phỏng vấn Backend Intern theo chính hồ sơ của bạn
            </h1>
            <p className="mt-6 max-w-xl text-base leading-7 text-pretty text-slate-600 sm:text-lg">
              Từ CV đến buổi luyện, báo cáo và tiến bộ — mỗi giai đoạn có một nơi riêng để bạn dễ tập trung.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-4">
              <Link href="/prepare" className="rounded-xl bg-blue-700 px-5 py-3 text-sm font-semibold text-white shadow-[0_14px_26px_-17px_rgba(29,78,216,0.9)] transition hover:-translate-y-0.5 hover:bg-blue-800 active:translate-y-0">
                Bắt đầu chuẩn bị hồ sơ
              </Link>
              <span className="text-sm text-slate-500">Khoảng 5–10 phút cho lần thiết lập đầu tiên</span>
            </div>
          </div>

          <aside className="relative overflow-hidden rounded-2xl border border-blue-100 bg-blue-50/60 p-5 shadow-[0_18px_38px_-34px_rgba(37,85,199,0.72)]" aria-label="Thông tin phiên luyện tập">
            <span className="absolute -top-9 -right-8 size-24 rounded-full bg-blue-200/45 blur-2xl" aria-hidden="true" />
            <p className="relative text-xs font-bold tracking-[0.13em] text-blue-700 uppercase">Hôm nay bạn sẽ luyện</p>
            <p className="relative mt-2 text-lg font-semibold tracking-tight text-slate-950">Backend Developer Intern</p>
            <p className="relative mt-2 text-sm leading-6 text-slate-600">Phỏng vấn tiếng Việt · CV tiếng Việt hoặc tiếng Anh</p>
          </aside>
        </section>

        <section className="enter-up enter-up-delay-1 mt-14" aria-labelledby="journey-title">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="text-xs font-bold tracking-[0.13em] text-blue-700 uppercase">Cách hoạt động</p>
              <h2 id="journey-title" className="mt-2 text-2xl font-bold tracking-[-0.03em] text-slate-950">Từng bước rõ ràng, không lẫn việc</h2>
            </div>
            <Link href="/prepare" className="text-sm font-semibold text-blue-700 hover:text-blue-900">Tiếp tục với CV →</Link>
          </div>

          <ol className="mt-6 divide-y divide-slate-200/80 overflow-hidden rounded-2xl border border-slate-200 bg-white/90 shadow-[0_18px_38px_-34px_rgba(37,85,199,0.42)]">
            {journey.map((step) => (
              <li key={step.number} className="grid gap-3 p-5 transition-colors hover:bg-blue-50/40 sm:grid-cols-[3rem_minmax(0,1fr)_minmax(0,1.35fr)] sm:items-baseline sm:gap-5">
                <span className="font-mono text-xs font-bold tracking-[0.16em] text-blue-700 tabular-nums">{step.number}</span>
                <h3 className="text-base font-semibold tracking-tight text-slate-950">{step.title}</h3>
                <p className="text-sm leading-6 text-slate-600">{step.detail}</p>
              </li>
            ))}
          </ol>
        </section>
      </main>
    </AppFrame>
  );
}
