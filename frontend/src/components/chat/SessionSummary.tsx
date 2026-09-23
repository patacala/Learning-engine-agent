import type { TrainingProposal } from '../../types/training';

interface Props {
  proposals: TrainingProposal[];
}

export function SessionSummary({ proposals }: Props) {
  const approved = proposals.filter((p) => p.status === 'approved').length;
  const rejected = proposals.filter((p) => p.status === 'rejected').length;
  const pending = proposals.filter((p) => p.status === 'pending').length;

  return (
    <p className="text-[13px] text-[#6e6e80] mb-3">
      {approved} approved · {rejected} rejected · {pending} pending
    </p>
  );
}
