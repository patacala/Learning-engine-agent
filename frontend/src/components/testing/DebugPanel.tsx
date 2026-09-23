import { useState } from 'react';
import type { TestDebugInfo } from '../../types/testing';

interface Props {
  debug: TestDebugInfo;
}

function relevance(distance: number | null): string {
  if (distance == null) return '';
  const pct = Math.max(0, Math.min(100, Math.round((1 - distance) * 100)));
  return `${pct}%`;
}

export function DebugPanel({ debug }: Props) {
  const [open, setOpen] = useState(false);
  const [showAllRules, setShowAllRules] = useState(false);

  const retrieved = debug.knowledge_retrieved || [];
  const identity = debug.identity_loaded || {};
  const learning = debug.learning_context || {};

  return (
    <div className="mt-2 border border-[#d6d6d6] rounded-lg overflow-hidden bg-[#fcfcfc]">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-3 py-2 text-[12px] font-medium text-[#0d0d0d] hover:bg-[#f4f4f4] transition-colors"
      >
        <span>🔍 Qué usó el agente (entrenamiento, conocimiento, estrategia)</span>
        <svg
          width="12"
          height="12"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          className={`transition-transform ${open ? 'rotate-180' : ''}`}
        >
          <path d="M6 9l6 6 6-6" />
        </svg>
      </button>

      {open && (
        <div className="px-3 py-2.5 space-y-3 border-t border-[#ececec] bg-[#fafafa]">
          {/* Knowledge retrieved */}
          <div>
            <p className="text-[10px] uppercase tracking-wider text-[#b3b3b3] mb-1">
              Retrieved knowledge
            </p>
            {retrieved.length === 0 ? (
              <p className="text-[12px] text-[#6e6e80]">None</p>
            ) : (
              <div className="space-y-1.5">
                {retrieved.map((doc, i) => (
                  <div key={i} className="text-[12px] text-[#0d0d0d]">
                    <div className="flex items-center gap-1.5">
                      <span
                        className={`text-[9px] uppercase px-1.5 py-0.5 rounded-full ${
                          doc.source === 'scenario'
                            ? 'bg-[#0d0d0d] text-white'
                            : 'bg-[#ececec] text-[#6e6e80]'
                        }`}
                      >
                        {doc.source === 'scenario' ? 'Scenario' : 'Agent'}
                      </span>
                      <span className="font-medium truncate">{doc.title || 'Untitled'}</span>
                      {doc.distance != null && (
                        <span className="text-[10px] text-[#b3b3b3] ml-auto tabular-nums">
                          {relevance(doc.distance)}
                        </span>
                      )}
                    </div>
                    <p className="text-[11px] text-[#6e6e80] mt-0.5 line-clamp-2">{doc.excerpt}</p>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Injected into prompt */}
          {debug.knowledge_injected?.length > 0 && (
            <div>
              <p className="text-[10px] uppercase tracking-wider text-[#b3b3b3] mb-1">
                Injected into prompt
              </p>
              <ul className="space-y-0.5">
                {debug.knowledge_injected.map((p, i) => (
                  <li key={i} className="text-[11px] text-[#6e6e80] line-clamp-2">
                    • {p}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Identity loaded */}
          {(identity.principles?.length || identity.values?.length || identity.name) && (
            <div>
              <p className="text-[10px] uppercase tracking-wider text-[#b3b3b3] mb-1">
                Identity loaded
              </p>
              {identity.name && (
                <p className="text-[12px] text-[#0d0d0d]">{identity.name}</p>
              )}
              {identity.principles?.length ? (
                <p className="text-[11px] text-[#6e6e80] mt-0.5">
                  Principles: {identity.principles.join(', ')}
                </p>
              ) : null}
            </div>
          )}

          {/* Learned knowledge actually injected into this reply (Cognitive Learning Engine) */}
          <div>
            <p className="text-[10px] uppercase tracking-wider text-[#b3b3b3] mb-1">
              Trained knowledge used in this reply
            </p>
            {!learning.would_inject ? (
              <p className="text-[12px] text-[#6e6e80]">
                No trained play/expression matched this message.
              </p>
            ) : (
              <div className="space-y-1.5">
                {learning.proven_plays?.map((p, i) => {
                  const n = p.occurrence_count ?? 1;
                  // Below 3 samples, success_rate is just 0%/50%/100% — not a
                  // real rate. Show the real avg_score and say how many times
                  // it's been seen instead of a misleading "100% éxito".
                  const label =
                    n >= 3
                      ? `${Math.round(p.success_rate * 100)}% éxito en ${n} casos`
                      : `visto ${n === 1 ? '1 vez' : `${n} veces`} · ${Math.round(
                          (p.avg_score ?? p.success_rate) * 100,
                        )}% efectividad`;
                  return (
                    <div key={`play-${i}`} className="text-[12px] text-[#0d0d0d]">
                      <span className="text-[9px] uppercase px-1.5 py-0.5 rounded-full bg-[#e8f7ee] text-[#1a7f4a] mr-1.5">
                        {p.move_kind} · {label}
                      </span>
                      <span className="text-[11px] text-[#6e6e80]">{p.excerpt}</span>
                    </div>
                  );
                })}
                {learning.winning_expressions?.map((e, i) => (
                  <p key={`win-${i}`} className="text-[11px] text-[#1a7f4a]">
                    ✓ &ldquo;{e}&rdquo;
                  </p>
                ))}
                {learning.anti_expressions?.map((e, i) => (
                  <p key={`anti-${i}`} className="text-[11px] text-[#b3261e]">
                    ✗ &ldquo;{e}&rdquo;
                  </p>
                ))}
                {learning.behavior_rules && learning.behavior_rules.length > 0 && (
                  <div>
                    {(showAllRules
                      ? learning.behavior_rules
                      : learning.behavior_rules.slice(0, 3)
                    ).map((r, i) => (
                      <p key={`rule-${i}`} className="text-[11px] text-[#6e6e80]">
                        Regla: {r}
                      </p>
                    ))}
                    {learning.behavior_rules.length > 3 && (
                      <button
                        onClick={() => setShowAllRules((v) => !v)}
                        className="text-[11px] text-[#0d0d0d] underline mt-0.5"
                      >
                        {showAllRules
                          ? 'Ver menos'
                          : `+${learning.behavior_rules.length - 3} reglas más relevantes a este mensaje`}
                      </button>
                    )}
                  </div>
                )}
              </div>
            )}
            <p className="text-[10px] text-[#b3b3b3] mt-1 italic">
              This is what the trained agent actually used to write this reply — nothing is
              persisted, but the response above reflects your approved training.
            </p>
          </div>

          {/* Strategy + analysis */}
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-[#6e6e80]">
            {debug.strategy?.strategy_type && (
              <span>Strategy: {debug.strategy.strategy_type}</span>
            )}
            {debug.analysis?.intent && <span>Intent: {debug.analysis.intent}</span>}
            {debug.analysis?.sentiment && <span>Sentiment: {debug.analysis.sentiment}</span>}
            {debug.route && <span>Route: {debug.route}</span>}
            {debug.execution?.total_tokens ? (
              <span>Tokens: {debug.execution.total_tokens}</span>
            ) : null}
          </div>
        </div>
      )}
    </div>
  );
}
