export interface CategoryConfig {
  id: string;
  label: string;
  shortLabel: string;
  description: string;
  icon: string;
  /** Singular label for proposal cards */
  singularLabel: string;
}

export const IDENTITY_SUBTYPES = [
  'identity:principle',
  'identity:belief',
  'identity:value',
  'identity:words_never_use',
  'identity:words_prefer',
] as const;

export const IDENTITY_SUBTYPE_LABELS: Record<string, string> = {
  principle: 'Principle',
  belief: 'Belief',
  value: 'Value',
  words_never_use: 'Avoid Words',
  words_prefer: 'Preferred Words',
};

export const CATEGORY_ORDER = [
  'technique',
  'objection_handling',
  'needs_discovery',
  'closing',
  'signal',
  'identity',
] as const;

export type CategoryId = (typeof CATEGORY_ORDER)[number];

/** Region order for the neural map (bilateral layout) */
export const MAP_REGION_ORDER = [
  'technique',
  'identity',
  'needs_discovery',
  'signal',
  'objection_handling',
  'closing',
] as const;

export const CATEGORY_CONFIG: Record<string, CategoryConfig> = {
  technique: {
    id: 'technique',
    label: 'Techniques',
    shortLabel: 'TECH',
    singularLabel: 'Technique',
    description: 'Sales tactics and conversational techniques the agent has learned.',
    icon: 'M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z',
  },
  objection_handling: {
    id: 'objection_handling',
    label: 'Objection Handling',
    shortLabel: 'OBJ',
    singularLabel: 'Objection',
    description: 'Responses and reframes for common buyer objections.',
    icon: 'M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z',
  },
  needs_discovery: {
    id: 'needs_discovery',
    label: 'Discovery',
    shortLabel: 'DISC',
    singularLabel: 'Discovery',
    description: 'Questions and approaches for uncovering customer needs.',
    icon: 'M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z',
  },
  closing: {
    id: 'closing',
    label: 'Closing',
    shortLabel: 'CLOSE',
    singularLabel: 'Closing',
    description: 'Patterns for advancing deals toward commitment.',
    icon: 'M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z',
  },
  signal: {
    id: 'signal',
    label: 'Signals',
    shortLabel: 'SIGNAL',
    singularLabel: 'Signal',
    description: 'Buying signals and conversational cues to watch for.',
    icon: 'M13 10V3L4 14h7v7l9-11h-7z',
  },
  identity: {
    id: 'identity',
    label: 'Identity',
    shortLabel: 'IDENTITY',
    singularLabel: 'Identity',
    description: 'Principles, beliefs, values, and language preferences.',
    icon: 'M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z',
  },
  // --- Conversation move kinds (evidence-based learning) ---
  greeting: {
    id: 'greeting', label: 'Greeting', shortLabel: 'GREET', singularLabel: 'Greeting',
    description: 'Opening moves that set the tone.',
    icon: 'M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 3v-3z',
  },
  discovery: {
    id: 'discovery', label: 'Discovery', shortLabel: 'DISC', singularLabel: 'Discovery',
    description: 'Questions that uncover customer needs.',
    icon: 'M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z',
  },
  needs_diagnosis: {
    id: 'needs_diagnosis', label: 'Needs Diagnosis', shortLabel: 'NEEDS', singularLabel: 'Needs Diagnosis',
    description: 'Diagnostic probing of the real need.',
    icon: 'M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z',
  },
  qualification: {
    id: 'qualification', label: 'Qualification', shortLabel: 'QUAL', singularLabel: 'Qualification',
    description: 'Qualifying fit and readiness.',
    icon: 'M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z',
  },
  value_prop: {
    id: 'value_prop', label: 'Value Prop', shortLabel: 'VALUE', singularLabel: 'Value Prop',
    description: 'Framing product value.',
    icon: 'M13 10V3L4 14h7v7l9-11h-7z',
  },
  social_proof: {
    id: 'social_proof', label: 'Social Proof', shortLabel: 'PROOF', singularLabel: 'Social Proof',
    description: 'Using others’ experience to persuade.',
    icon: 'M17 20h5v-2a4 4 0 00-3-3.87M9 20H4v-2a4 4 0 013-3.87m6-1.13a4 4 0 10-4-4 4 4 0 004 4z',
  },
  reframe: {
    id: 'reframe', label: 'Reframe', shortLabel: 'REFRAME', singularLabel: 'Reframe',
    description: 'Reshaping the customer’s perspective.',
    icon: 'M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15',
  },
  urgency: {
    id: 'urgency', label: 'Urgency', shortLabel: 'URGENT', singularLabel: 'Urgency',
    description: 'Creating timely momentum.',
    icon: 'M13 10V3L4 14h7v7l9-11h-7z',
  },
  follow_up: {
    id: 'follow_up', label: 'Follow-up', shortLabel: 'FOLLOW', singularLabel: 'Follow-up',
    description: 'Re-engaging and nurturing.',
    icon: 'M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4',
  },
};

export const FALLBACK_CATEGORY_ICON =
  'M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z';

export function getCategoryConfig(type: string): CategoryConfig {
  if (type.startsWith('identity:')) {
    const sub = type.replace('identity:', '');
    return {
      id: 'identity',
      label: IDENTITY_SUBTYPE_LABELS[sub] || sub,
      shortLabel: 'IDENTITY',
      singularLabel: IDENTITY_SUBTYPE_LABELS[sub] || sub,
      description: CATEGORY_CONFIG.identity.description,
      icon: CATEGORY_CONFIG.identity.icon,
    };
  }
  return (
    CATEGORY_CONFIG[type] || {
      id: type,
      label: type,
      shortLabel: type.slice(0, 6).toUpperCase(),
      singularLabel: type,
      description: '',
      icon: FALLBACK_CATEGORY_ICON,
    }
  );
}

export type MaturityLevel = 'empty' | 'emerging' | 'growing' | 'mature';

export function maturityFromFill(fill: number): MaturityLevel {
  if (fill <= 0) return 'empty';
  if (fill < 0.34) return 'emerging';
  if (fill < 0.67) return 'growing';
  return 'mature';
}

export const MATURITY_LABELS: Record<MaturityLevel, string> = {
  empty: 'Empty',
  emerging: 'Emerging',
  growing: 'Growing',
  mature: 'Mature',
};
