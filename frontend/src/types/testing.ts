export interface TemporaryDocument {
  id: string;
  title: string;
  content: string;
  category: string;
}

export interface Scenario {
  id: string;
  agent_version_id: string | null;
  name: string;
  company_name: string;
  documents: TemporaryDocument[];
  quick_facts: Record<string, string>;
  created_at?: string;
}

export interface TestTurn {
  role: 'user' | 'assistant';
  content: string;
}

export interface RetrievedDocument {
  title: string;
  excerpt: string;
  category: string;
  source: 'scenario' | 'permanent';
  distance: number | null;
}

export interface TestDebugInfo {
  knowledge_retrieved: RetrievedDocument[];
  knowledge_injected: string[];
  identity_loaded: {
    name?: string;
    communication_style?: string;
    principles?: string[];
    beliefs?: string[];
    values?: string[];
    words_never_use?: string[];
    words_prefer?: string[];
  };
  strategy: {
    strategy_type?: string;
    tactic_instruction?: string;
    reasoning?: string;
    scores?: Record<string, number>;
  };
  analysis: {
    intent?: string;
    sentiment?: string;
    language?: string;
    stage?: string;
    urgency?: string;
    risk?: string;
  };
  route: string;
  execution: {
    nodes?: number;
    total_ms?: number;
    llm_calls?: number;
    total_tokens?: number;
  };
  // What the Cognitive Learning Engine surfaced and injected into the actual
  // prompt for this turn — the Test Playground runs the same trained-agent
  // pipeline as a real conversation (just without persisting anything), so
  // this reflects why `response` looks the way it does.
  learning_context: {
    would_inject?: boolean;
    proven_plays?: {
      move_kind: string;
      success_rate: number;
      avg_score?: number;
      occurrence_count?: number;
      excerpt: string;
    }[];
    winning_expressions?: string[];
    anti_expressions?: string[];
    behavior_rules?: string[];
    prompt_block_preview?: string;
  };
}

export interface TestMessageResponse {
  response: string;
  voice_ssml: string | null;
  debug: TestDebugInfo;
}

export interface TestChatMessage {
  role: 'user' | 'assistant';
  content: string;
  debug?: TestDebugInfo;
}
