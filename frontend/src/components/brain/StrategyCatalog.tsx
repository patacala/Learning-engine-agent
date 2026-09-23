import { useEffect, useState } from 'react';
import { getStrategyCatalog, type StrategyCatalog as StrategyCatalogData } from '../../api/trainingApi';

interface Props {
  agentVersionId: string;
}

/** Surfaces what StrategyEngine actually runs for this agent — default (generic,
 * built-in, not editable here) or custom (this agent's own, from agent_strategies).
 * Exists so "why did the agent say that" doesn't require reading source code. */
export function StrategyCatalog({ agentVersionId }: Props) {
  const [data, setData] = useState<StrategyCatalogData | null>(null);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    getStrategyCatalog(agentVersionId)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [agentVersionId]);

  if (loading) return null;
  if (!data) return null;

  return (
    <div>
      <p className="text-[11px] text-[var(--text-secondary)] uppercase tracking-[0.12em] mb-1.5">
        Strategy Catalog
      </p>
      <div
        className={`text-[12px] rounded-2xl px-4 py-3 mb-2.5 border ${
          data.mode === 'default'
            ? 'bg-[#fdf0e8] border-[#f0d5bf] text-[#8a4a10]'
            : 'bg-[var(--surface)] border-[var(--border)] text-[var(--text-secondary)]'
        }`}
      >
        {data.mode === 'default' ? '⚠️ ' : '✓ '}
        {data.note}
      </div>
      <div className="space-y-2">
        {data.strategies.map((s) => (
          <div
            key={s.strategy_type}
            className="bg-[var(--surface)] border border-[var(--border)] rounded-2xl overflow-hidden"
          >
            <button
              type="button"
              onClick={() => setExpanded(expanded === s.strategy_type ? null : s.strategy_type)}
              className="w-full flex items-center justify-between px-4 py-2.5 text-left"
            >
              <span className="text-[13px] text-[var(--text-primary)]">
                {s.name}{' '}
                <span
                  className={`text-[9px] uppercase px-1.5 py-0.5 rounded-full ml-1 ${
                    s.source === 'default'
                      ? 'bg-[#fdf0e8] text-[#8a4a10]'
                      : 'bg-[#e6f4ea] text-[#137333]'
                  }`}
                >
                  {s.source}
                </span>
              </span>
              <svg
                className={`w-3.5 h-3.5 text-[var(--text-muted)] transition-transform ${
                  expanded === s.strategy_type ? 'rotate-180' : ''
                }`}
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                <path d="M6 9l6 6 6-6" />
              </svg>
            </button>
            {expanded === s.strategy_type && (
              <div className="px-4 pb-3 pt-0.5 border-t border-[var(--border-subtle)] space-y-1.5">
                {s.tactics.map((t, i) => (
                  <p key={i} className="text-[12px] text-[var(--text-secondary)]">
                    <span className="font-medium text-[var(--text-primary)]">{t.name}:</span>{' '}
                    {t.prompt_instruction}
                  </p>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
