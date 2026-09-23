import type { TrainingSession } from '../../types/training';

interface Props {
  session: TrainingSession;
  isActive: boolean;
  onClick: () => void;
  onDelete: () => void;
}

export function SessionListItem({ session, isActive, onClick, onDelete }: Props) {
  const label = session.source_label || 'Untitled session';

  return (
    <div
      className={`group flex items-center rounded-lg cursor-pointer transition-colors mb-0.5 ${
        isActive ? 'bg-[#e3e3e3]' : 'hover:bg-[#ececec]'
      }`}
    >
      <button
        onClick={onClick}
        className="flex-1 text-left px-2.5 py-2 min-w-0"
      >
        <div className="text-[13px] text-[#0d0d0d] truncate leading-snug">{label}</div>
      </button>
      <button
        onClick={(e) => { e.stopPropagation(); onDelete(); }}
        className="opacity-0 group-hover:opacity-100 px-2 py-1 text-[13px] text-[#6e6e80] hover:text-[#0d0d0d] transition-opacity mr-1"
        title="Delete"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <path d="M3 6h18M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6" />
        </svg>
      </button>
    </div>
  );
}
