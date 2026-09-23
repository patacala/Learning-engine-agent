import { useState } from 'react';
import type { TrainingProposal } from '../../types/training';
import { getCategoryConfig } from '../../constants/categories';

interface Props {
  proposal: TrainingProposal;
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
  onEditAndApprove: (id: string, content: string, title?: string) => void;
}

export function PatternCard({ proposal, onApprove, onReject, onEditAndApprove }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editTitle, setEditTitle] = useState(proposal.title);
  const [editContent, setEditContent] = useState(proposal.content);

  const config = getCategoryConfig(proposal.pattern_type);
  const isPending = proposal.status === 'pending';
  const isApproved = proposal.status === 'approved';
  const isRejected = proposal.status === 'rejected';
  const isMove = !!proposal.polarity;
  const isAnti = proposal.polarity === 'negative';

  const startEdit = (e: React.MouseEvent) => {
    e.stopPropagation();
    setEditTitle(proposal.title);
    setEditContent(proposal.content);
    setEditing(true);
    setExpanded(true);
  };

  const cancelEdit = () => {
    setEditing(false);
  };

  const saveAndApprove = (e: React.MouseEvent) => {
    e.stopPropagation();
    onEditAndApprove(proposal.id, editContent, editTitle !== proposal.title ? editTitle : undefined);
    setEditing(false);
  };

  return (
    <div
      className={`bg-white border border-[#e3e3e3] rounded-2xl mb-2.5 overflow-hidden transition-shadow hover:shadow-sm ${
        isRejected ? 'opacity-50' : ''
      }`}
    >
      {/* Card header */}
      <div
        onClick={() => !editing && setExpanded(!expanded)}
        className="flex items-center gap-3.5 px-4 py-3.5 cursor-pointer"
      >
        {/* Type icon */}
        <div className="w-10 h-10 rounded-full bg-[#f4f4f4] flex items-center justify-center flex-shrink-0">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#0d0d0d" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <path d={config.icon} />
          </svg>
        </div>

        {/* Title + type label */}
        <div className="flex-1 min-w-0">
          {editing ? (
            <input
              value={editTitle}
              onChange={(e) => setEditTitle(e.target.value)}
              onClick={(e) => e.stopPropagation()}
              className="text-[15px] text-[#0d0d0d] w-full border border-[#e3e3e3] rounded-lg px-2.5 py-1 focus:border-[#b3b3b3] focus:outline-none"
            />
          ) : (
            <>
              <div className="flex items-center gap-1.5 min-w-0">
                {isMove && (
                  <span
                    className="text-[9px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded flex-shrink-0"
                    style={{
                      background: isAnti ? '#fce8e8' : '#e6f4ea',
                      color: isAnti ? '#a50e0e' : '#137333',
                    }}
                  >
                    {isAnti ? 'Anti-pattern' : 'Pattern'}
                  </span>
                )}
                <p className="text-[15px] text-[#0d0d0d] leading-snug truncate">{proposal.title}</p>
              </div>
              <p className="text-[12px] text-[#6e6e80] mt-0.5 truncate">
                {config.singularLabel} · {Math.round(proposal.confidence * 100)}%
                {isMove && proposal.client_state_after && (
                  <span>
                    {' · '}
                    {proposal.client_state_before || '—'} → {proposal.client_state_after}
                  </span>
                )}
              </p>
            </>
          )}
        </div>

        {/* Action icons */}
        <div className="flex items-center gap-0.5 flex-shrink-0" onClick={(e) => e.stopPropagation()}>
          {isPending && !editing && (
            <>
              {/* Approve */}
              <button
                onClick={() => onApprove(proposal.id)}
                className="w-7 h-7 rounded-full flex items-center justify-center hover:bg-[#f4f4f4] transition-colors"
                title="Approve"
              >
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#0d0d0d" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M20 6L9 17l-5-5" />
                </svg>
              </button>
              {/* Edit — hidden for moves (evidence is verbatim) */}
              {!isMove && (
                <button
                  onClick={startEdit}
                  className="w-7 h-7 rounded-full flex items-center justify-center hover:bg-[#f4f4f4] transition-colors"
                  title="Edit"
                >
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#0d0d0d" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M17 3a2.828 2.828 0 114 4L7.5 20.5 2 22l1.5-5.5L17 3z" />
                  </svg>
                </button>
              )}
              {/* Reject */}
              <button
                onClick={() => onReject(proposal.id)}
                className="w-7 h-7 rounded-full flex items-center justify-center hover:bg-[#f4f4f4] transition-colors"
                title="Reject"
              >
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#0d0d0d" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M18 6L6 18M6 6l12 12" />
                </svg>
              </button>
            </>
          )}
          {isApproved && (
            <div className="w-7 h-7 rounded-full bg-[#0d0d0d] flex items-center justify-center">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M20 6L9 17l-5-5" />
              </svg>
            </div>
          )}
          {isRejected && (
            <div className="w-7 h-7 rounded-full bg-[#e3e3e3] flex items-center justify-center">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#6e6e80" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M18 6L6 18M6 6l12 12" />
              </svg>
            </div>
          )}
          {!editing && (
            <svg
              className={`w-4 h-4 text-[#b3b3b3] ml-0.5 transition-transform ${expanded ? 'rotate-180' : ''}`}
              viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"
            >
              <path d="M6 9l6 6 6-6" />
            </svg>
          )}
        </div>
      </div>

      {/* Expanded content */}
      {expanded && (
        <div className="px-4 pb-4 pt-1 border-t border-[#f0f0f0]">
          {editing ? (
            <div className="mt-2">
              <textarea
                value={editContent}
                onChange={(e) => setEditContent(e.target.value)}
                rows={4}
                className="w-full text-[15px] text-[#0d0d0d] border border-[#e3e3e3] rounded-xl px-3 py-2.5 resize-y focus:border-[#b3b3b3] focus:outline-none leading-[1.6]"
              />
              <div className="flex items-center gap-3 mt-3">
                <button
                  onClick={saveAndApprove}
                  className="text-[13px] font-medium text-white bg-[#0d0d0d] px-4 py-1.5 rounded-full hover:bg-[#2d2d2d] transition-colors"
                >
                  Save & Approve
                </button>
                <button
                  onClick={cancelEdit}
                  className="text-[13px] text-[#6e6e80] hover:text-[#0d0d0d] transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <>
              <p className="text-[15px] text-[#374151] whitespace-pre-wrap leading-[1.6] mt-2">{proposal.content}</p>
              {proposal.raw_excerpt && (
                <p className="mt-3 text-[13px] text-[#6e6e80] italic leading-[1.5] pl-3 border-l-2 border-[#e3e3e3]">
                  "{proposal.raw_excerpt}"
                </p>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
