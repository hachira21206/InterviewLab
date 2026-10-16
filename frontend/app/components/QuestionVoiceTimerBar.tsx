'use client';
import { useState, useEffect, useRef } from 'react';
import { QuestionDifficulty } from '../types/interview';

interface QuestionVoiceTimerBarProps {
  questionId: string;
  difficulty: QuestionDifficulty;
  disabled: boolean;
  onAppendSpeech: (spokenText: string) => void;
}

const RECOMMENDED_SECONDS: Record<QuestionDifficulty, number> = {
  easy: 120,
  medium: 180,
  hard: 240,
};

function formatClock(totalSec: number): string {
  const m = Math.floor(totalSec / 60);
  const s = totalSec % 60;
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

export default function QuestionVoiceTimerBar({
  questionId,
  difficulty,
  disabled,
  onAppendSpeech,
}: QuestionVoiceTimerBarProps) {
  const [elapsedSec, setElapsedSec] = useState(0);
  const [paused, setPaused] = useState(false);
  const [recording, setRecording] = useState(false);
  const [previewSpeech, setPreviewSpeech] = useState('');
  const [voiceNotice, setVoiceNotice] = useState<string | null>(null);

  const activeQuestionRef = useRef(questionId);
  const speechEngineRef = useRef<{ stop: () => void } | null>(null);
  const appendCallbackRef = useRef(onAppendSpeech);

  useEffect(() => {
    appendCallbackRef.current = onAppendSpeech;
  }, [onAppendSpeech]);

  useEffect(() => {
    const id = window.setInterval(() => {
      if (activeQuestionRef.current !== questionId) {
        activeQuestionRef.current = questionId;
        setElapsedSec(0);
        setPaused(false);
        return;
      }
      if (!paused && !disabled) {
        setElapsedSec((prev) => prev + 1);
      }
    }, 1000);
    return () => window.clearInterval(id);
  }, [questionId, paused, disabled]);

  useEffect(() => {
    return () => {
      if (speechEngineRef.current) {
        try {
          speechEngineRef.current.stop();
        } catch {
          // ignore
        }
        speechEngineRef.current = null;
      }
    };
  }, [questionId]);

  const stopSpeechEngine = () => {
    if (speechEngineRef.current) {
      try {
        speechEngineRef.current.stop();
      } catch {
        // ignore
      }
      speechEngineRef.current = null;
    }
    setRecording(false);
    setPreviewSpeech('');
  };

  const toggleSpeechEngine = () => {
    setVoiceNotice(null);
    if (recording) {
      stopSpeechEngine();
      return;
    }

    const win = window as unknown as Record<string, unknown>;
    const EngineCtor = (win.SpeechRecognition || win.webkitSpeechRecognition) as
      | (new () => Record<string, unknown>)
      | undefined;

    if (!EngineCtor) {
      setVoiceNotice(
        'Trình duyệt hiện tại chưa hỗ trợ nhập giọng nói trực tiếp. Vui lòng dùng Chrome hoặc Edge.'
      );
      return;
    }

    try {
      const instance = new EngineCtor();
      instance.lang = 'vi-VN';
      instance.continuous = true;
      instance.interimResults = true;

      instance.onresult = (ev: unknown) => {
        const eventObj = ev as {
          resultIndex: number;
          results: { length: number; [idx: number]: { isFinal: boolean; 0: { transcript: string } } };
        };
        let committed = '';
        let draft = '';
        for (let i = eventObj.resultIndex; i < eventObj.results.length; i++) {
          const item = eventObj.results[i];
          const textPiece = item?.[0]?.transcript || '';
          if (item.isFinal) {
            committed += textPiece + ' ';
          } else {
            draft += textPiece;
          }
        }
        if (committed.trim()) {
          appendCallbackRef.current(committed.trim());
        }
        setPreviewSpeech(draft);
      };

      instance.onerror = () => {
        setVoiceNotice('Không thể thu âm từ micro. Vui lòng kiểm tra quyền truy cập micro trên trình duyệt.');
        setRecording(false);
        setPreviewSpeech('');
      };

      instance.onend = () => {
        setRecording(false);
        setPreviewSpeech('');
      };

      speechEngineRef.current = instance as unknown as { stop: () => void };
      (instance as unknown as { start: () => void }).start();
      setRecording(true);
    } catch {
      setVoiceNotice('Không thể khởi động tính năng nhận diện giọng nói.');
      setRecording(false);
    }
  };

  const targetSec = RECOMMENDED_SECONDS[difficulty] || 180;
  const isOverTime = elapsedSec > targetSec;
  const progressPercent = Math.min((elapsedSec / targetSec) * 100, 100);

  return (
    <div className="mb-5 space-y-2.5">
      <div className="rounded-xl border border-slate-200 bg-slate-50/80 p-3.5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-[13rem] flex-1">
            <div className="flex items-center justify-between gap-3">
              <p className="text-xs font-semibold text-slate-700">Nhịp trả lời</p>
              <span className={`font-mono text-xs font-bold tabular-nums ${isOverTime ? 'text-amber-800' : 'text-blue-800'}`}>
                {formatClock(elapsedSec)} <span className="font-medium text-slate-400">/ {formatClock(targetSec)}</span>
              </span>
            </div>
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-200" role="progressbar" aria-label="Thời gian trả lời khuyến nghị" aria-valuenow={Math.round(progressPercent)} aria-valuemin={0} aria-valuemax={100}>
              <div className={`h-full rounded-full transition-[width,background-color] duration-500 ${isOverTime ? 'bg-amber-500' : 'bg-blue-600'}`} style={{ width: `${progressPercent}%` }} />
            </div>
          </div>
          <div className="flex items-center gap-1.5">
            <button type="button" onClick={() => setPaused((p) => !p)} disabled={disabled} className="rounded-lg px-2.5 py-1.5 text-xs font-semibold text-slate-600 hover:bg-white disabled:opacity-50" aria-label={paused ? 'Tiếp tục đồng hồ' : 'Tạm dừng đồng hồ'}>
              {paused ? '▶ Tiếp tục' : 'Ⅱ Tạm dừng'}
            </button>
            <button type="button" onClick={() => setElapsedSec(0)} disabled={disabled} className="rounded-lg px-2.5 py-1.5 text-xs font-semibold text-slate-500 hover:bg-white disabled:opacity-50">
              Đặt lại
            </button>
          </div>
        </div>
        <p className="mt-2 text-[11px] text-slate-500">Thời gian tham khảo cho câu {difficulty === 'easy' ? 'cơ bản' : difficulty === 'medium' ? 'trung bình' : 'nâng cao'}.</p>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-blue-100 bg-blue-50/55 px-3.5 py-2.5">
        <div>
          <p className="text-xs font-semibold text-blue-950">Trả lời bằng giọng nói</p>
          <p className="mt-0.5 text-[11px] text-blue-800/75">Văn bản nhận diện sẽ được thêm vào câu trả lời bên dưới.</p>
        </div>
        <button
          type="button"
          onClick={toggleSpeechEngine}
          disabled={disabled}
          className={`inline-flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-xs font-semibold transition-colors ${
            recording
              ? 'animate-pulse bg-red-600 text-white hover:bg-red-700'
              : 'border border-blue-200 bg-blue-50 text-blue-800 hover:bg-blue-100'
          } disabled:cursor-not-allowed disabled:opacity-50`}
        >
          {recording ? '■ Dừng ghi âm' : '🎙 Bắt đầu nói'}
        </button>
      </div>

      {isOverTime && (
        <p className="text-xs text-amber-700">
          Lưu ý: Bạn đã vượt thời gian khuyến nghị cho câu hỏi này ({formatClock(targetSec)}), nhưng vẫn có thể hoàn thiện câu trả lời trước khi gửi.
        </p>
      )}

      {recording && (
        <div className="rounded-lg border border-red-200 bg-red-50/70 px-3 py-2 text-xs text-red-900" role="status">
          <span className="font-semibold">Đang nghe tiếng Việt: </span>
          <span className="italic">
            {previewSpeech || 'Hãy nói vào micro, văn bản sẽ tự động điền vào ô trả lời bên dưới...'}
          </span>
        </div>
      )}

      {voiceNotice && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
          {voiceNotice}
        </div>
      )}
    </div>
  );
}
