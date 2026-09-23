import type { Agent } from '../../types/training';

interface Props {
  agents: Agent[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

export function AgentSelector({ agents, selectedId, onSelect }: Props) {
  return (
    <div className="px-3 pb-2">
      <select
        value={selectedId || ''}
        onChange={(e) => onSelect(e.target.value)}
        className="w-full bg-transparent text-[13px] text-[#0d0d0d] border border-[#e3e3e3] rounded-lg px-2.5 py-1.5 focus:border-[#b3b3b3] focus:outline-none appearance-none cursor-pointer"
      >
        <option value="" disabled>
          Select agent...
        </option>
        {agents.map((a) => (
          <option key={a.id} value={a.id}>
            {a.name}
          </option>
        ))}
      </select>
    </div>
  );
}
