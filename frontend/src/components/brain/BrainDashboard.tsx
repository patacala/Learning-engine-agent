import { useEffect, useRef, useState } from 'react';
import type { AgentBrain } from '../../types/training';
import { CATEGORY_CONFIG, CATEGORY_ORDER } from '../../constants/categories';
import {
  computeRegionMetrics,
  getLearnedForCategory,
  type BrainRegionMetrics,
} from '../../constants/brainMetrics';
import { BrainSvg } from './BrainSvg';
import { LearnedAggregates } from './LearnedAggregates';
import { StrategyCatalog } from './StrategyCatalog';

interface Props {
  brain: AgentBrain | null;
  loading: boolean;
  error: string | null;
  agentVersionId: string | null;
}

function KnowledgeCard({
  categoryId,
  brain,
  metrics,
  expanded,
  onToggle,
  cardRef,
}: {
  categoryId: string;
  brain: AgentBrain;
  metrics: BrainRegionMetrics | undefined;
  expanded: boolean;
  onToggle: () => void;
  cardRef: (el: HTMLDivElement | null) => void;
}) {
  const cfg = CATEGORY_CONFIG[categoryId];
  const [expandedItemId, setExpandedItemId] = useState<string | null>(null);
  if (!cfg) return null;

  const items = getLearnedForCategory(brain, categoryId);
  const hasItems = items.length > 0;
  const docs = metrics?.documents || 0;
  const patterns = metrics?.patterns || 0;
  const target = metrics?.target || 8;
  const fillPct = Math.round((metrics?.fill || 0) * 100);

  return (
    <div
      ref={cardRef}
      id={`knowledge-card-${categoryId}`}
      className={`bg-[var(--surface)] border rounded-2xl overflow-hidden transition-all duration-200 ${
        expanded
          ? 'border-[var(--text-primary)] shadow-[0_0_0_1px_rgba(13,13,13,0.06)]'
          : 'border-[var(--border)] hover:border-[var(--border-strong)]'
      }`}
    >
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={expanded}
        className="w-full flex items-center gap-3 px-4 py-3.5 cursor-pointer text-left"
      >
        <div
          className={`w-9 h-9 rounded-full flex items-center justify-center flex-shrink-0 ${
            hasItems || docs > 0 ? 'bg-[var(--surface-muted)]' : 'bg-[var(--surface-subtle)]'
          }`}
        >
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke={hasItems || docs > 0 ? 'var(--text-primary)' : 'var(--text-muted)'}
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d={cfg.icon} />
          </svg>
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <p className="text-[14px] text-[var(--text-primary)] font-medium">{cfg.label}</p>
            {metrics && patterns > 0 && (
              <span className="text-[10px] uppercase tracking-wider text-[var(--text-secondary)] bg-[var(--surface-muted)] px-1.5 py-0.5 rounded-full">
                {metrics.maturityLabel}
              </span>
            )}
          </div>
          <p className="text-[12px] text-[var(--text-secondary)] mt-0.5">
            {patterns} of {target} patterns to mature
            {docs > 0 ? ` · ${docs} docs` : ''}
          </p>
          <div className="mt-2.5 flex items-center gap-2.5">
            <div
              className="maturity-bar flex-1"
              role="progressbar"
              aria-valuenow={patterns}
              aria-valuemin={0}
              aria-valuemax={target}
              aria-label={`${cfg.label} maturity`}
            >
              <div className="maturity-bar__fill" style={{ width: `${fillPct}%` }} />
            </div>
            <span className="text-[11px] tabular-nums text-[var(--text-muted)] w-8 text-right">
              {fillPct}%
            </span>
          </div>
        </div>
        <svg
          className={`w-4 h-4 text-[var(--text-muted)] flex-shrink-0 transition-transform ${
            expanded ? 'rotate-180' : ''
          }`}
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
        >
          <path d="M6 9l6 6 6-6" />
        </svg>
      </button>

      {expanded && (
        <div className="border-t border-[var(--border-subtle)]">
          <p className="px-4 pt-3 pb-1 text-[12px] text-[var(--text-secondary)] leading-relaxed">
            {cfg.description}
          </p>
          {hasItems ? (
            items.map((item) => (
              <div key={item.id} className="border-b border-[var(--border-subtle)] last:border-b-0">
                <button
                  type="button"
                  onClick={() => setExpandedItemId(expandedItemId === item.id ? null : item.id)}
                  className="w-full text-left px-4 py-2.5 flex items-center gap-2 hover:bg-[var(--surface-subtle)] transition-colors"
                >
                  <div className="w-5 h-5 rounded-full bg-[var(--text-primary)] flex items-center justify-center flex-shrink-0">
                    <svg
                      width="10"
                      height="10"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="white"
                      strokeWidth="2.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <path d="M20 6L9 17l-5-5" />
                    </svg>
                  </div>
                  <span className="text-[14px] text-[var(--text-primary)] flex-1 truncate">
                    {item.title}
                  </span>
                  <svg
                    className={`w-3.5 h-3.5 text-[var(--text-muted)] flex-shrink-0 transition-transform ${
                      expandedItemId === item.id ? 'rotate-180' : ''
                    }`}
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                  >
                    <path d="M6 9l6 6 6-6" />
                  </svg>
                </button>
                {expandedItemId === item.id && (
                  <div className="px-4 pb-3 pl-11">
                    <p className="text-[13px] text-[var(--text-secondary)] leading-[1.6] whitespace-pre-wrap">
                      {item.content}
                    </p>
                  </div>
                )}
              </div>
            ))
          ) : (
            <p className="px-4 py-3 text-[13px] text-[var(--text-muted)]">
              No approved patterns yet. Train the agent to grow this area.
            </p>
          )}
        </div>
      )}
    </div>
  );
}

export function BrainDashboard({ brain, loading, error, agentVersionId }: Props) {
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const cardRefs = useRef<Record<string, HTMLDivElement | null>>({});

  useEffect(() => {
    if (!selectedCategory) return;
    const el = cardRefs.current[selectedCategory];
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }, [selectedCategory]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <svg className="w-5 h-5 animate-spin text-[var(--text-secondary)]" viewBox="0 0 24 24" fill="none">
          <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2" opacity="0.2" />
          <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        </svg>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-[15px] text-[var(--text-secondary)]">{error}</p>
      </div>
    );
  }

  if (!brain) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-[15px] text-[var(--text-secondary)]">Select an agent</p>
      </div>
    );
  }

  const regions = computeRegionMetrics(brain);
  const metricsById = new Map(regions.map((r) => [r.id, r]));
  const totalLearned = brain.training.approved;
  const totalKnowledge = Object.values(brain.knowledge).reduce((a, b) => a + b, 0);

  const handleSelectCategory = (id: string) => {
    setSelectedCategory((prev) => (prev === id ? null : id));
  };

  return (
    <div className="flex-1 overflow-y-auto px-4 py-6">
      <div className="max-w-[960px] mx-auto">
        <div className="mb-6">
          <h2 className="text-[20px] font-semibold text-[var(--text-primary)] tracking-tight">
            Agent Knowledge
          </h2>
          <p className="text-[13px] text-[var(--text-secondary)] mt-1">
            {brain.identity?.name || 'Agent'} — {totalLearned} patterns learned across{' '}
            {brain.training.total_sessions} sessions
          </p>
        </div>

        <div className="flex flex-col lg:flex-row gap-6 lg:gap-8 items-stretch lg:items-start">
          {/* Neural map */}
          <div className="w-full lg:w-[300px] flex-shrink-0">
            <div className="knowledge-map-panel rounded-2xl border border-[rgba(255,255,255,0.08)] p-5 flex flex-col items-center">
              <p className="text-[11px] text-white/45 uppercase tracking-[0.14em] mb-3">
                Knowledge Map
              </p>
              <BrainSvg
                regions={regions}
                selectedId={selectedCategory}
                onSelect={handleSelectCategory}
              />
              <div className="mt-4 pt-4 border-t border-white/8 w-full text-center">
                <p className="text-[28px] font-semibold text-white/95 tracking-tight">
                  {totalKnowledge}
                </p>
                <p className="text-[11px] text-white/45 mt-0.5">Indexed documents</p>
                <p className="text-[11px] text-white/30 mt-1">
                  Distinct from approved training patterns
                </p>
              </div>
            </div>
          </div>

          {/* Details */}
          <div className="flex-1 min-w-0 space-y-4">
            <div className="grid grid-cols-3 gap-3">
              {(
                [
                  ['Sessions', brain.training.total_sessions],
                  ['Approved', brain.training.approved],
                  ['Pending', brain.training.pending],
                ] as const
              ).map(([label, value]) => (
                <div
                  key={label}
                  className="bg-[var(--surface)] border border-[var(--border)] rounded-2xl px-4 py-3.5 text-center"
                >
                  <p className="text-[22px] font-semibold text-[var(--text-primary)] tracking-tight">
                    {value}
                  </p>
                  <p className="text-[12px] text-[var(--text-secondary)] mt-0.5">{label}</p>
                </div>
              ))}
            </div>

            <div>
              <p className="text-[11px] text-[var(--text-secondary)] uppercase tracking-[0.12em] mb-1.5">
                Knowledge Areas
              </p>
              <p className="text-[12px] text-[var(--text-muted)] mb-2.5">
                Each bar shows progress toward 8 approved patterns in that area.
              </p>
              <div className="space-y-2.5">
                {CATEGORY_ORDER.map((id) => (
                  <KnowledgeCard
                    key={id}
                    categoryId={id}
                    brain={brain}
                    metrics={metricsById.get(id)}
                    expanded={selectedCategory === id}
                    onToggle={() => handleSelectCategory(id)}
                    cardRef={(el) => {
                      cardRefs.current[id] = el;
                    }}
                  />
                ))}
              </div>
            </div>

            {brain.identity &&
              (brain.identity.principles.length > 0 ||
                brain.identity.beliefs.length > 0 ||
                brain.identity.values.length > 0) && (
                <div>
                  <p className="text-[11px] text-[var(--text-secondary)] uppercase tracking-[0.12em] mb-2.5">
                    Identity Profile
                  </p>
                  <div className="bg-[var(--surface)] border border-[var(--border)] rounded-2xl p-4 space-y-3.5">
                    {brain.identity.communication_style && (
                      <div>
                        <p className="text-[12px] text-[var(--text-secondary)] mb-1">
                          Communication Style
                        </p>
                        <p className="text-[14px] text-[var(--text-primary)]">
                          {brain.identity.communication_style}
                        </p>
                      </div>
                    )}
                    {brain.identity.principles.length > 0 && (
                      <div>
                        <p className="text-[12px] text-[var(--text-secondary)] mb-1.5">Principles</p>
                        <div className="flex flex-wrap gap-1.5">
                          {brain.identity.principles.map((p, i) => (
                            <span key={i} className="knowledge-pill">
                              {p}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                    {brain.identity.beliefs.length > 0 && (
                      <div>
                        <p className="text-[12px] text-[var(--text-secondary)] mb-1.5">Beliefs</p>
                        <div className="flex flex-wrap gap-1.5">
                          {brain.identity.beliefs.map((b, i) => (
                            <span key={i} className="knowledge-pill">
                              {b}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                    {brain.identity.values.length > 0 && (
                      <div>
                        <p className="text-[12px] text-[var(--text-secondary)] mb-1.5">Values</p>
                        <div className="flex flex-wrap gap-1.5">
                          {brain.identity.values.map((v, i) => (
                            <span key={i} className="knowledge-pill">
                              {v}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                    {brain.identity.words_prefer.length > 0 && (
                      <div>
                        <p className="text-[12px] text-[var(--text-secondary)] mb-1.5">
                          Preferred Words
                        </p>
                        <div className="flex flex-wrap gap-1.5">
                          {brain.identity.words_prefer.map((w, i) => (
                            <span key={i} className="knowledge-pill">
                              {w}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                    {brain.identity.words_never_use.length > 0 && (
                      <div>
                        <p className="text-[12px] text-[var(--text-secondary)] mb-1.5">
                          Words to Avoid
                        </p>
                        <div className="flex flex-wrap gap-1.5">
                          {brain.identity.words_never_use.map((w, i) => (
                            <span key={i} className="knowledge-pill knowledge-pill--muted">
                              {w}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}

            <LearnedAggregates brain={brain} />

            {agentVersionId && <StrategyCatalog agentVersionId={agentVersionId} />}
          </div>
        </div>
      </div>
    </div>
  );
}
