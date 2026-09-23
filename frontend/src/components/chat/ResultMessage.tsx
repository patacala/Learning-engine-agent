import type { TrainingResult } from '../../types/training';
import { PatternCard } from '../proposals/PatternCard';

interface Props {
  result: TrainingResult;
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
  onEditAndApprove: (id: string, content: string, title?: string) => void;
  onApproveAll: () => void;
}

export function ResultMessage({ result, onApprove, onReject, onEditAndApprove, onApproveAll }: Props) {
  const pendingCount = result.proposals.filter((p) => p.status === 'pending').length;
  const approved = result.proposals.filter((p) => p.status === 'approved').length;

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <p className="text-[15px] text-[#0d0d0d]">
            {result.patterns_extracted} patterns extracted
            {result.source_label ? ` — ${result.source_label}` : ''}
          </p>
          <p className="text-[13px] text-[#6e6e80] mt-0.5">
            {approved} approved · {pendingCount} pending
          </p>
        </div>
        {pendingCount > 0 && (
          <button
            onClick={onApproveAll}
            className="text-[13px] text-[#0d0d0d] border border-[#e3e3e3] rounded-full px-3.5 py-1.5 hover:bg-[#f4f4f4] transition-colors"
          >
            Approve all ({pendingCount})
          </button>
        )}
      </div>

      {/* Cards */}
      <div>
        {result.proposals.map((p) => (
          <PatternCard
            key={p.id}
            proposal={p}
            onApprove={onApprove}
            onReject={onReject}
            onEditAndApprove={onEditAndApprove}
          />
        ))}
      </div>
    </div>
  );
}
