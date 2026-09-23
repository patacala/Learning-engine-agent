import type { AgentBrain } from '../../types/training';

interface Props {
  brain: AgentBrain;
}

function pct(v: number): string {
  return `${Math.round((v || 0) * 100)}%`;
}

/** Evidence-based aggregates: style, competing clusters, expressions, insights. */
export function LearnedAggregates({ brain }: Props) {
  const style = brain.style;
  const clusters = (brain.clusters || []).filter((c) => c.polarity === 'positive').slice(0, 5);
  const winning = (brain.expressions || []).filter((e) => e.polarity === 'winning').slice(0, 6);
  const anti = (brain.expressions || []).filter((e) => e.polarity === 'anti').slice(0, 6);
  const insights = brain.insights || [];

  const hasAny =
    style || clusters.length || winning.length || anti.length || insights.length;
  if (!hasAny) return null;

  return (
    <div className="space-y-5">
      {style && (
        <Section title="Communication Style">
          <div className="bg-[var(--surface)] border border-[var(--border)] rounded-2xl p-4 space-y-2">
            {(
              [
                ['Empathy', style.empathy_level],
                ['Questions', style.question_ratio],
                ['Formality', style.formality],
                ['Technical', style.technical_level],
                ['Sales pressure', style.sales_pressure],
              ] as const
            ).map(([label, v]) => (
              <div key={label} className="flex items-center gap-3">
                <span className="text-[12px] text-[var(--text-secondary)] w-28 flex-shrink-0">
                  {label}
                </span>
                <div className="flex-1 h-1.5 bg-white/10 rounded-full overflow-hidden">
                  <div className="h-full bg-white/80" style={{ width: pct(v) }} />
                </div>
                <span className="text-[11px] text-[var(--text-muted)] w-8 text-right">{pct(v)}</span>
              </div>
            ))}
            {style.microexpressions.length > 0 && (
              <div className="pt-2 flex flex-wrap gap-1.5">
                {style.microexpressions.map((m) => (
                  <span key={m.phrase} className="knowledge-pill">
                    {m.phrase} · {pct(m.frequency)}
                  </span>
                ))}
              </div>
            )}
          </div>
        </Section>
      )}

      {clusters.length > 0 && (
        <Section title="Top Plays (by success rate)">
          <div className="space-y-2">
            {clusters.map((c) => (
              <div
                key={c.id}
                className="bg-[var(--surface)] border border-[var(--border)] rounded-xl p-3"
              >
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-[10px] text-[var(--text-muted)] bg-white/5 rounded px-1.5 py-0.5">
                    #{c.rank}
                  </span>
                  <span className="text-[11px] text-[var(--text-secondary)]">{c.move_kind}</span>
                  <span className="ml-auto text-[12px] font-semibold text-[#4ade80]">
                    {pct(c.success_rate)} · {c.occurrence_count}×
                  </span>
                </div>
                <p className="text-[13px] text-[var(--text-primary)] line-clamp-2">
                  {c.canonical_excerpt}
                </p>
              </div>
            ))}
          </div>
        </Section>
      )}

      {(winning.length > 0 || anti.length > 0) && (
        <Section title="Expressions">
          <div className="grid sm:grid-cols-2 gap-3">
            <ExprList label="Winning" tone="good" items={winning.map((e) => e.exact_phrase)} />
            <ExprList label="Avoid" tone="bad" items={anti.map((e) => e.exact_phrase)} />
          </div>
        </Section>
      )}

      {insights.length > 0 && (
        <Section title="Insights">
          <div className="space-y-2">
            {insights.map((ins) => (
              <div
                key={ins.id}
                className="bg-[var(--surface)] border border-[var(--border)] rounded-xl p-3"
              >
                <div className="flex items-center gap-2 mb-1">
                  <span
                    className={`text-[9px] uppercase px-1.5 py-0.5 rounded ${
                      ins.status === 'published'
                        ? 'bg-[#4ade80]/15 text-[#4ade80]'
                        : 'bg-white/8 text-[var(--text-muted)]'
                    }`}
                  >
                    {ins.status}
                  </span>
                  <span className="text-[11px] text-[var(--text-muted)]">
                    {ins.sample_size} samples
                  </span>
                </div>
                <p className="text-[13px] text-[var(--text-primary)]">{ins.insight_text}</p>
                {ins.behavior_rule && (
                  <p className="text-[12px] text-[var(--text-secondary)] mt-1">
                    → {ins.behavior_rule}
                  </p>
                )}
              </div>
            ))}
          </div>
        </Section>
      )}
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="text-[11px] text-[var(--text-secondary)] uppercase tracking-[0.12em] mb-2">
        {title}
      </p>
      {children}
    </div>
  );
}

function ExprList({ label, tone, items }: { label: string; tone: 'good' | 'bad'; items: string[] }) {
  const color = tone === 'good' ? '#4ade80' : '#f87171';
  return (
    <div className="bg-[var(--surface)] border border-[var(--border)] rounded-xl p-3">
      <p className="text-[11px] mb-1.5" style={{ color }}>
        {label}
      </p>
      {items.length === 0 ? (
        <p className="text-[12px] text-[var(--text-muted)]">—</p>
      ) : (
        <ul className="space-y-1">
          {items.map((p, i) => (
            <li key={i} className="text-[13px] text-[var(--text-primary)] leading-snug">
              “{p}”
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
