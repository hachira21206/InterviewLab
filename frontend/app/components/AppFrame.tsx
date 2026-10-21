import Link from 'next/link';
import type { ReactNode } from 'react';

type AppFrameProps = {
  children: ReactNode;
  current?: 'home' | 'prepare' | 'analysis' | 'practice' | 'interview' | 'result' | 'report' | 'progress';
};

const NAV_ITEMS: Array<{
  href: string;
  label: string;
  key: NonNullable<AppFrameProps['current']>;
  step?: string;
}> = [
  { href: '/', label: 'Trang chủ', key: 'home' },
  { href: '/prepare', label: 'Hồ sơ', key: 'prepare', step: '01' },
  { href: '/analysis', label: 'Phân tích', key: 'analysis', step: '02' },
  { href: '/practice', label: 'Chọn bài', key: 'practice', step: '03' },
  { href: '/interview', label: 'Làm bài', key: 'interview', step: '04' },
  { href: '/result', label: 'Kết quả', key: 'result', step: '05' },
  { href: '/report', label: 'Báo cáo', key: 'report', step: '06' },
  { href: '/progress', label: 'Tiến bộ', key: 'progress', step: '07' },
];

export default function AppFrame({ children, current }: AppFrameProps) {
  return (
    <div className="app-background min-h-[100dvh] text-slate-900">
      <a href="#main-content" className="skip-link">
        Đi tới nội dung chính
      </a>

      <header className="sticky top-0 z-40 border-b border-slate-200/80 bg-white/82 backdrop-blur-xl">
        <div className="app-container flex flex-wrap items-center justify-between gap-3 py-3">
          <Link href="/" className="group flex items-center gap-3 rounded-xl focus-visible:outline-none">
            <span
              className="grid size-10 shrink-0 place-items-center rounded-[0.85rem] bg-[linear-gradient(145deg,#2f63d5,#183b91)] text-sm font-bold tracking-tight text-white shadow-[0_12px_25px_-14px_rgba(29,78,216,0.85)] transition-transform duration-200 group-hover:scale-105"
              aria-hidden="true"
            >
              IL
            </span>
            <span>
              <span className="block text-[0.68rem] font-bold tracking-[0.18em] text-blue-700 uppercase">
                Interview Lab
              </span>
              <span className="block text-sm font-medium text-slate-700">
                Luyện phỏng vấn Backend Intern
              </span>
            </span>
          </Link>

          <nav
            className="journey-scroll nav-scroll-cue flex max-w-full items-center gap-1 overflow-x-auto py-0.5"
            aria-label="Điều hướng chính"
          >
            {NAV_ITEMS.map(({ href, label, key, step }) => {
              const isActive = current === key;
              return (
                <Link
                  key={href}
                  href={href}
                  className={`inline-flex shrink-0 snap-start items-center gap-1.5 rounded-xl px-3 py-2 text-sm font-semibold transition-all ${
                    isActive
                      ? 'bg-blue-600 text-white shadow-[0_8px_20px_-10px_rgba(37,99,235,0.85)]'
                      : 'text-slate-600 hover:bg-slate-100/90 hover:text-slate-950'
                  }`}
                >
                  {step && (
                    <span
                      className={`font-mono text-[10px] font-bold tabular-nums ${
                        isActive ? 'text-blue-100' : 'text-blue-600/80'
                      }`}
                    >
                      {step}
                    </span>
                  )}
                  <span>{label}</span>
                </Link>
              );
            })}
          </nav>
        </div>
      </header>

      {children}
    </div>
  );
}
