import { useState, useRef, useCallback, useEffect } from 'react';

const MAX_AUDIO_MB = 25;
const MAX_AUDIO_BYTES = MAX_AUDIO_MB * 1024 * 1024;

interface Props {
  disabled: boolean;
  processingStage: string | null;
  onSubmit: (transcript: string, audio?: File) => void;
}

export function TranscriptInput({ disabled, processingStage, onSubmit }: Props) {
  const [text, setText] = useState('');
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const autoResize = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 200) + 'px';
  }, []);

  useEffect(() => {
    autoResize();
  }, [text, autoResize]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] || null;
    if (file && file.size > MAX_AUDIO_BYTES) {
      setFileError(`File too large (max ${MAX_AUDIO_MB}MB)`);
      setAudioFile(null);
      if (fileRef.current) fileRef.current.value = '';
      return;
    }
    setFileError(null);
    setAudioFile(file);
  };

  const handleSubmit = useCallback(() => {
    if (disabled) return;
    if (!text.trim() && !audioFile) return;
    onSubmit(text, audioFile || undefined);
    setText('');
    setAudioFile(null);
    setFileError(null);
  }, [text, audioFile, disabled, onSubmit]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const canSubmit = !disabled && (text.trim() || audioFile);

  return (
    <div className="w-full max-w-[768px] mx-auto">
      {processingStage && (
        <div className="flex items-center gap-2 text-[13px] text-[#6e6e80] mb-2 px-1">
          <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
            <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2" opacity="0.2" />
            <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
          {processingStage}
        </div>
      )}

      {fileError && <p className="text-[13px] text-[#6e6e80] mb-1 px-1">{fileError}</p>}

      {audioFile && (
        <div className="flex items-center gap-2 mb-1.5 px-1">
          <span className="text-[13px] text-[#6e6e80]">{audioFile.name}</span>
          <button
            onClick={() => { setAudioFile(null); setFileError(null); if (fileRef.current) fileRef.current.value = ''; }}
            className="text-[13px] text-[#6e6e80] hover:text-[#0d0d0d]"
          >
            &times;
          </button>
        </div>
      )}

      <div className="relative flex items-end border border-[#e3e3e3] rounded-3xl bg-[#f4f4f4] px-3 py-2 focus-within:border-[#b3b3b3] transition-colors shadow-sm">
        {/* Audio clip button */}
        <input
          ref={fileRef}
          type="file"
          accept="audio/*,.mp3,.mp4,.m4a,.wav,.webm"
          className="hidden"
          onChange={handleFileChange}
        />
        <button
          type="button"
          onClick={() => fileRef.current?.click()}
          disabled={disabled}
          className="flex-shrink-0 w-8 h-8 flex items-center justify-center rounded-full text-[#6e6e80] hover:text-[#0d0d0d] hover:bg-[#e3e3e3] disabled:opacity-40 transition-colors mr-1"
          title="Attach audio"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48" />
          </svg>
        </button>

        <textarea
          ref={textareaRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          placeholder="Paste expert sales transcript..."
          rows={1}
          className="flex-1 text-[15px] text-[#0d0d0d] resize-none border-0 outline-none bg-transparent placeholder-[#8e8ea0] disabled:opacity-50 min-h-[24px] max-h-[200px] py-1 leading-[1.5]"
        />

        {/* Send button */}
        <button
          onClick={handleSubmit}
          disabled={!canSubmit}
          className={`flex-shrink-0 w-8 h-8 flex items-center justify-center rounded-full transition-colors ml-1 ${
            canSubmit
              ? 'bg-[#0d0d0d] text-white hover:bg-[#2d2d2d]'
              : 'bg-[#d7d7d7] text-white cursor-not-allowed'
          }`}
          title="Send (Cmd+Enter)"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 3l0 18M12 3l-7 7M12 3l7 7" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" fill="none" />
          </svg>
        </button>
      </div>
    </div>
  );
}
