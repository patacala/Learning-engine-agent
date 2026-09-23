import type { Agent, TrainingSession } from '../../types/training';
import { AgentSelector } from './AgentSelector';
import { SessionListItem } from './SessionListItem';

export type SidebarView = 'training' | 'brain' | 'testing';

interface Props {
  agents: Agent[];
  selectedAgentId: string | null;
  sessions: TrainingSession[];
  activeSessionId: string | null;
  currentView: SidebarView;
  onSelectAgent: (id: string) => void;
  onSelectSession: (id: string) => void;
  onDeleteSession: (id: string) => void;
  onNewSession: () => void;
  onChangeView: (view: SidebarView) => void;
}

export function SessionSidebar({
  agents,
  selectedAgentId,
  sessions,
  activeSessionId,
  currentView,
  onSelectAgent,
  onSelectSession,
  onDeleteSession,
  onNewSession,
  onChangeView,
}: Props) {
  return (
    <>
      {/* Header */}
      <div className="flex items-center justify-between px-3 pt-3 pb-2">
        <span className="text-[14px] font-semibold text-[#0d0d0d]">Learn</span>
        {selectedAgentId && currentView === 'training' && (
          <button
            onClick={onNewSession}
            className="w-7 h-7 flex items-center justify-center rounded-lg hover:bg-[#ececec] transition-colors"
            title="New session"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <path d="M12 5v14M5 12h14" />
            </svg>
          </button>
        )}
      </div>

      <AgentSelector agents={agents} selectedId={selectedAgentId} onSelect={onSelectAgent} />

      {selectedAgentId && (
        <>
          {/* Tabs */}
          <div className="flex px-3 gap-1 mb-1">
            <button
              onClick={() => onChangeView('training')}
              className={`px-2.5 py-1 text-[12px] rounded-md transition-colors ${
                currentView === 'training'
                  ? 'bg-[#ececec] text-[#0d0d0d] font-medium'
                  : 'text-[#6e6e80] hover:bg-[#ececec]'
              }`}
            >
              Sessions
            </button>
            <button
              onClick={() => onChangeView('brain')}
              className={`px-2.5 py-1 text-[12px] rounded-md transition-colors ${
                currentView === 'brain'
                  ? 'bg-[#ececec] text-[#0d0d0d] font-medium'
                  : 'text-[#6e6e80] hover:bg-[#ececec]'
              }`}
            >
              Brain
            </button>
            <button
              onClick={() => onChangeView('testing')}
              className={`px-2.5 py-1 text-[12px] rounded-md transition-colors ${
                currentView === 'testing'
                  ? 'bg-[#ececec] text-[#0d0d0d] font-medium'
                  : 'text-[#6e6e80] hover:bg-[#ececec]'
              }`}
            >
              Test
            </button>
          </div>

          {currentView === 'training' && (
            <div className="flex-1 overflow-y-auto px-2 mt-1">
              {sessions.length === 0 && (
                <p className="text-[13px] text-[#6e6e80] px-2 py-4 text-center">No sessions yet</p>
              )}
              {sessions.map((s) => (
                <SessionListItem
                  key={s.id}
                  session={s}
                  isActive={s.id === activeSessionId}
                  onClick={() => onSelectSession(s.id)}
                  onDelete={() => onDeleteSession(s.id)}
                />
              ))}
            </div>
          )}
        </>
      )}
    </>
  );
}
