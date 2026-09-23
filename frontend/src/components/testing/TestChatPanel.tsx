import { useCallback, useEffect, useRef, useState } from 'react';
import type { TestChatMessage } from '../../types/testing';
import { DebugPanel } from './DebugPanel';

interface Props {
  messages: TestChatMessage[];
  isLoading: boolean;
  error: string | null;
  hasAgent: boolean;
  companyName: string;
  onSend: (message: string) => void;
  onClear: () => void;
  onSendToTraining: () => void;
  isSendingToTraining: boolean;
}

export function TestChatPanel({
  messages,
  isLoading,
  error,
  hasAgent,
  companyName,
  onSend,
  onClear,
  onSendToTraining,
  isSendingToTraining,
}: Props) {
  const [input, setInput] = useState('');
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  const autoResize = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 200) + 'px';
  }, []);

  useEffect(() => {
    autoResize();
  }, [input, autoResize]);

  const submit = () => {
    if (!input.trim() || isLoading) return;
    onSend(input.trim());
    setInput('');
  };

  const canSubmit = hasAgent && !isLoading && !!input.trim();

  return (
    <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-[#ececec]">
        <div className="min-w-0">
          <span className="text-[14px] font-semibold text-[#0d0d0d]">Test playground</span>
          {companyName && (
            <span className="text-[12px] text-[#6e6e80] ml-2">· {companyName}</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {messages.length > 0 && (
            <>
              <button
                onClick={onSendToTraining}
                type="button"
                disabled={isSendingToTraining}
                className="text-[12px] text-[#6e6e80] hover:text-[#0d0d0d] border border-[#e3e3e3] rounded-md px-2 py-1 transition-colors disabled:opacity-50"
              >
                {isSendingToTraining ? 'Sending…' : 'Send to Training'}
              </button>
              <button
                onClick={onClear}
                className="text-[12px] text-[#6e6e80] hover:text-[#0d0d0d] transition-colors"
              >
                Clear
              </button>
            </>
          )}
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-[720px] mx-auto px-4 py-6">
          {!hasAgent && (
            <p className="text-[15px] text-[#6e6e80] text-center py-16">
              Select an agent to start testing
            </p>
          )}

          {hasAgent && messages.length === 0 && !error && (
            <p className="text-[15px] text-[#6e6e80] text-center py-16">
              Set up the business context on the right and type as if you were a client.
            </p>
          )}

          {messages.map((m, i) => (
            <div key={i} className="mb-4">
              <div className={m.role === 'user' ? 'flex justify-end' : 'flex justify-start'}>
                <div
                  className={`max-w-[85%] rounded-2xl px-3.5 py-2 text-[14px] ${
                    m.role === 'user'
                      ? 'bg-[#0d0d0d] text-white'
                      : 'bg-[#f4f4f4] text-[#0d0d0d]'
                  }`}
                >
                  {m.content}
                </div>
              </div>
              {m.role === 'assistant' && m.debug && <DebugPanel debug={m.debug} />}
            </div>
          ))}

          {isLoading && (
            <div className="flex justify-start mb-4">
              <div className="bg-[#f4f4f4] rounded-2xl px-3.5 py-2.5">
                <svg className="w-4 h-4 animate-spin text-[#6e6e80]" viewBox="0 0 24 24" fill="none">
                  <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2" opacity="0.2" />
                  <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                </svg>
              </div>
            </div>
          )}

          {error && (
            <div className="text-[14px] text-[#6e6e80] border border-[#e3e3e3] rounded-xl px-4 py-3">
              {error}
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      </div>

      {/* Composer */}
      <div className="px-4 pb-4 pt-2">
        <div className="w-full max-w-[720px] mx-auto">
          <div className="relative flex items-end border border-[#e3e3e3] rounded-3xl bg-[#f4f4f4] px-3 py-2 focus-within:border-[#b3b3b3] transition-colors shadow-sm">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  submit();
                }
              }}
              disabled={!hasAgent || isLoading}
              placeholder="Type a message as a client..."
              rows={1}
              className="flex-1 text-[15px] text-[#0d0d0d] resize-none border-0 outline-none bg-transparent placeholder-[#8e8ea0] disabled:opacity-50 min-h-[24px] max-h-[200px] py-1 leading-[1.5]"
            />

            <button
              onClick={submit}
              disabled={!canSubmit}
              className={`flex-shrink-0 w-8 h-8 flex items-center justify-center rounded-full transition-colors ml-1 ${
                canSubmit
                  ? 'bg-[#0d0d0d] text-white hover:bg-[#2d2d2d]'
                  : 'bg-[#d7d7d7] text-white cursor-not-allowed'
              }`}
              title="Send (Enter)"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 3l0 18M12 3l-7 7M12 3l7 7" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" fill="none" />
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
