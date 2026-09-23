export interface Agent {
  id: string;
  name: string;
  agent_type: string;
  description: string;
}

export interface TrainingSession {
  id: string;
  agent_version_id: string;
  source_label: string;
  source_type: string;
  status: string;
  patterns_extracted: number;
  patterns_approved: number;
  created_at: string;
}

export interface TrainingProposal {
  id: string;
  session_id: string | null;
  agent_version_id: string;
  pattern_type: string;
  title: string;
  content: string;
  raw_excerpt: string;
  confidence: number;
  status: string;
  knowledge_document_id?: string | null;
  // Move-specific fields (evidence-based learning)
  polarity?: 'positive' | 'negative';
  client_state_before?: string;
  client_state_after?: string;
  score?: number;
  outcome_label?: string;
}

export interface TrainingResult {
  session_id: string;
  source_label: string;
  transcript: string;
  patterns_extracted: number;
  proposals: TrainingProposal[];
}

export type SSEStage =
  | 'transcribing'
  | 'extracting'
  | 'analyzing'
  | 'creating_proposals'
  | 'completed'
  | 'error';

export interface SSEEvent {
  stage: SSEStage;
  result?: TrainingResult;
  message?: string;
}

export interface LearnedItem {
  id: string;
  title: string;
  content: string;
}

export interface AgentBrain {
  identity: {
    name: string;
    description: string;
    communication_style: string;
    principles: string[];
    beliefs: string[];
    values: string[];
    words_never_use: string[];
    words_prefer: string[];
  } | null;
  knowledge: Record<string, number>;
  training: {
    total_sessions?: number;
    total_extracted: number;
    approved: number;
    rejected: number;
    pending: number;
  };
  learned: Record<string, LearnedItem[]>;
  clusters?: BrainCluster[];
  expressions?: BrainExpression[];
  style?: BrainStyle | null;
  insights?: BrainInsight[];
}

export interface BrainCluster {
  id: string;
  move_kind: string;
  polarity: string;
  canonical_excerpt: string;
  success_rate: number;
  occurrence_count: number;
  rank: number;
}

export interface BrainExpression {
  exact_phrase: string;
  polarity: string;
  success_rate: number;
  times_used: number;
}

export interface BrainStyle {
  empathy_level: number;
  question_ratio: number;
  formality: number;
  technical_level: number;
  sales_pressure: number;
  microexpressions: { phrase: string; frequency: number }[];
  prompt_block?: string;
  computed_from_n_conversations: number;
}

export interface BrainInsight {
  id: string;
  insight_text: string;
  behavior_rule: string;
  status: string;
  confidence: number;
  sample_size: number;
}
