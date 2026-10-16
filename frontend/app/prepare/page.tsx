import AppFrame from '../components/AppFrame';
import CVUpload from '../components/CVUpload';

export default function PreparePage() {
  return (
    <AppFrame current="prepare">
      <main id="main-content" className="app-container py-9 sm:py-14">
        <section className="enter-up mx-auto max-w-4xl">
          <div className="mb-8 max-w-2xl">
            <p className="text-xs font-bold tracking-[0.13em] text-blue-700 uppercase">Bước 01 · Bắt đầu tại đây</p>
            <h1 className="mt-3 text-3xl font-bold tracking-[-0.04em] text-slate-950 sm:text-4xl">Chuẩn bị hồ sơ phỏng vấn</h1>
            <p className="mt-3 text-base leading-7 text-slate-600">
              Tải CV, kiểm tra nội dung trích xuất và thêm mô tả công việc. Bạn luôn chủ động quyết định khi nào dữ liệu được gửi tới AI.
            </p>
          </div>

          <section className="surface-panel relative overflow-hidden rounded-[1.45rem] p-4 sm:p-8" aria-label="Biểu mẫu chuẩn bị hồ sơ">
            <div className="absolute top-0 right-0 h-28 w-44 bg-[radial-gradient(circle_at_top_right,rgba(191,219,254,0.42),transparent_70%)]" aria-hidden="true" />
            <div className="relative"><CVUpload mode="prepare" /></div>
          </section>
        </section>
      </main>
    </AppFrame>
  );
}
