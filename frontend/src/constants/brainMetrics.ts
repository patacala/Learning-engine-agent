import type { AgentBrain, LearnedItem } from '../types/training';
import {
  CATEGORY_CONFIG,
  IDENTITY_SUBTYPES,
  MAP_REGION_ORDER,
  MATURITY_LABELS,
  maturityFromFill,
} from './categories';

/** Approved patterns needed to fill the maturity bar completely. */
export const PATTERNS_FOR_MATURE = 8;

export interface BrainRegionMetrics {
  id: string;
  label: string;
  shortLabel: string;
  description: string;
  documents: number;
  patterns: number;
  /** Combined score for map intensity (patterns weighted) */
  score: number;
  /**
   * 0–1 bar fill: absolute progress toward PATTERNS_FOR_MATURE.
   * Independent per category — not relative to other areas.
   */
  fill: number;
  maturity: ReturnType<typeof maturityFromFill>;
  maturityLabel: string;
  /** Cap used for the bar label, e.g. "3 of 8" */
  target: number;
}

export function getLearnedForCategory(brain: AgentBrain, categoryId: string): LearnedItem[] {
  if (categoryId === 'identity') {
    const items: LearnedItem[] = [];
    for (const subtype of IDENTITY_SUBTYPES) {
      if (brain.learned[subtype]) {
        items.push(...brain.learned[subtype]);
      }
    }
    return items;
  }
  return brain.learned[categoryId] || [];
}

function documentCounts(brain: AgentBrain): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const [category, count] of Object.entries(brain.knowledge)) {
    const key = category.replace('training:', '');
    counts[key] = (counts[key] || 0) + count;
  }
  return counts;
}

function identityFieldCount(brain: AgentBrain): number {
  if (!brain.identity) return 0;
  return (
    brain.identity.principles.length +
    brain.identity.beliefs.length +
    brain.identity.values.length +
    brain.identity.words_prefer.length +
    brain.identity.words_never_use.length
  );
}

export function computeRegionMetrics(brain: AgentBrain): BrainRegionMetrics[] {
  const docs = documentCounts(brain);
  const idFields = identityFieldCount(brain);

  return MAP_REGION_ORDER.map((id) => {
    const cfg = CATEGORY_CONFIG[id];
    // Identity has no cluster-based "learned" patterns (agent_identity is
    // manually configured, not extracted by the learning pipeline) — use its
    // own field count so the bar reflects real data instead of being
    // permanently stuck at 0.
    const patterns = id === 'identity' ? idFields : getLearnedForCategory(brain, id).length;
    const documents = (docs[id] || 0) + (id === 'identity' ? idFields : 0);
    const score = documents + patterns * 2;
    // Absolute fill: how close this area is to a mature pattern set
    const fill = Math.min(patterns / PATTERNS_FOR_MATURE, 1);
    const maturity = maturityFromFill(patterns === 0 ? 0 : Math.max(fill, 0.08));

    return {
      id,
      label: cfg.label,
      shortLabel: cfg.shortLabel,
      description: cfg.description,
      documents,
      patterns,
      score,
      fill,
      maturity,
      maturityLabel: MATURITY_LABELS[maturity],
      target: PATTERNS_FOR_MATURE,
    };
  });
}
