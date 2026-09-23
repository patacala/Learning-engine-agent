import { useEffect, useRef } from 'react';
import type { TrainingResult } from '../../types/training';
import { TranscriptInput } from '../input/TranscriptInput';
import { ResultMessage } from './ResultMessage';

interface Props {
  currentResult: TrainingResult | null;
  processingStage: string | null;
  error: string | null;
  isLoading: boolean;
  hasAgent: boolean;
  activeSessionId: string | null;
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
  onEditAndApprove: (id: string, content: string, title?: string) => void;
  onApproveAll: () => void;
  onExtractDraft: (sessionId: string) => void;
  onSubmit: (transcript: string, audio?: File) => void;
}

export function ChatArea({
  currentResult,
  processingStage,
  error,
  isLoading,
  hasAgent,
  activeSessionId,
  onApprove,
  onReject,
  onEditAndApprove,
  onApproveAll,
  onExtractDraft,
  onSubmit,
}: Props) {
  const isEmptyDraft =
    !!activeSessionId &&
    !!currentResult &&
    currentResult.proposals.length === 0 &&
    !processingStage;
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [currentResult]);

  // Empty state: centered input
  if (!currentResult && !processingStage && !error) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center px-4">
        <h2 className="text-[22px] font-semibold text-[#0d0d0d] mb-6">
          {hasAgent ? 'What would you like to train?' : 'Select an agent to start'}
        </h2>
        {hasAgent && (
          <div className="w-full max-w-[768px]">
            <TranscriptInput
              disabled={isLoading || !hasAgent}
              processingStage={processingStage}
              onSubmit={onSubmit}
            />
          </div>
        )}
      </div>
    );
  }

  // Has results: scroll area + input at bottom
  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Scrollable results */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-[768px] mx-auto px-4 py-6">
          {error && (
            <div className="mb-4 text-[15px] text-[#6e6e80] border border-[#e3e3e3] rounded-xl px-4 py-3">
              {error}
            </div>
          )}

          {processingStage && !currentResult && (
            <div className="flex items-center justify-center py-16">
              <div className="text-center">
                <svg className="w-5 h-5 animate-spin mx-auto mb-3 text-[#6e6e80]" viewBox="0 0 24 24" fill="none">
                  <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2" opacity="0.2" />
                  <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                </svg>
                <p className="text-[15px] text-[#6e6e80]">{processingStage}</p>
              </div>
            </div>
          )}

          {isEmptyDraft && (
            <div className="text-center py-12">
              <p className="text-[15px] text-[#0d0d0d] mb-1">Borrador desde el playground</p>
              <p className="text-[13px] text-[#6e6e80] mb-4">
                This session has no patterns yet. Process it to extract them.
              </p>
              <button
                onClick={() => activeSessionId && onExtractDraft(activeSessionId)}
                className="text-[13px] font-medium text-white bg-[#0d0d0d] rounded-lg px-4 py-2 hover:bg-[#1a1a1a] transition-colors"
              >
                Procesar borrador
              </button>
            </div>
          )}

          {currentResult && !isEmptyDraft && (
            <ResultMessage
              result={currentResult}
              onApprove={onApprove}
              onReject={onReject}
              onEditAndApprove={onEditAndApprove}
              onApproveAll={onApproveAll}
            />
          )}
          <div ref={bottomRef} />
        </div>
      </div>

      {/* Input fixed at bottom */}
      <div className="px-4 pb-4 pt-2">
        <TranscriptInput
          disabled={isLoading || !hasAgent}
          processingStage={processingStage}
          onSubmit={onSubmit}
        />
      </div>
    </div>
  );
}
