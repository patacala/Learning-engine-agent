// API layer for the single "Learn" flow. Backed by /learning/* endpoints;
// moves are surfaced as approvable "proposals" so the shell UI is reused.
import type { Agent, AgentBrain, TrainingSession, TrainingProposal, TrainingResult, SSEEvent } from '../types/training';
import { apiFetch } from './http';

const BASE = '/api/v1';

export async function listAgents(): Promise<Agent[]> {
  const res = await apiFetch(`${BASE}/agents`);
  if (!res.ok) throw new Error('Failed to fetch agents');
  return res.json();
}

export async function listSessions(agentVersionId: string): Promise<TrainingSession[]> {
  const res = await apiFetch(`${BASE}/learning/sessions?agent_version_id=${agentVersionId}`);
  if (!res.ok) throw new Error('Failed to fetch sessions');
  return res.json();
}

export async function deleteSession(sessionId: string): Promise<void> {
  const res = await apiFetch(`${BASE}/learning/sessions/${sessionId}`, { method: 'DELETE' });
  if (!res.ok) throw new Error('Failed to delete session');
}

export async function listProposals(sessionId: string): Promise<TrainingProposal[]> {
  const res = await apiFetch(`${BASE}/learning/sessions/${sessionId}`);
  if (!res.ok) throw new Error('Failed to fetch session');
  const data = await res.json();
  return data.proposals ?? [];
}

export async function updateProposal(
  proposalId: string,
  status: 'approved' | 'rejected',
  _edits?: { content?: string; title?: string },
): Promise<Partial<TrainingProposal>> {
  // Moves are verbatim evidence — edits are ignored; only status changes.
  const res = await apiFetch(`${BASE}/learning/moves/${proposalId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status }),
  });
  if (!res.ok) throw new Error('Failed to update move');
  await res.json();
  return { status };
}

export async function batchUpdateProposals(
  proposalIds: string[],
  status: 'approved' | 'rejected',
): Promise<Array<{ id: string; status: string }>> {
  const res = await apiFetch(`${BASE}/learning/moves/batch`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ move_ids: proposalIds, status }),
  });
  if (!res.ok) throw new Error('Failed to batch update moves');
  await res.json();
  return proposalIds.map((id) => ({ id, status }));
}

export async function extractSession(sessionId: string): Promise<TrainingResult> {
  const res = await apiFetch(`${BASE}/learning/sessions/${sessionId}/extract`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error('Failed to process draft session');
  return res.json();
}

export async function getAgentBrain(agentVersionId: string): Promise<AgentBrain> {
  const res = await apiFetch(`${BASE}/agents/${agentVersionId}/brain`);
  if (!res.ok) throw new Error('Failed to fetch agent brain');
  return res.json();
}

export interface StrategyTactic {
  name: string;
  prompt_instruction: string;
}

export interface StrategyCatalogEntry {
  strategy_type: string;
  name: string;
  source: 'default' | 'custom';
  enabled: boolean;
  tactics: StrategyTactic[];
}

export interface StrategyCatalog {
  mode: 'default' | 'custom';
  note: string;
  strategies: StrategyCatalogEntry[];
}

export async function getStrategyCatalog(agentVersionId: string): Promise<StrategyCatalog> {
  const res = await apiFetch(`${BASE}/agents/${agentVersionId}/strategy-catalog`);
  if (!res.ok) throw new Error('Failed to fetch strategy catalog');
  return res.json();
}

export async function ingestTranscript(
  params: {
    agentVersionId: string;
    transcript?: string;
    audio?: File;
    sessionId?: string;
  },
  onStage: (stage: string) => void,
  onResult: (result: TrainingResult) => void,
  onError: (message: string) => void,
  signal?: AbortSignal,
): Promise<void> {
  const form = new FormData();
  form.append('agent_version_id', params.agentVersionId);
  if (params.transcript) form.append('transcript', params.transcript);
  if (params.audio) form.append('audio', params.audio);
  if (params.sessionId) form.append('session_id', params.sessionId);

  let res: Response;
  try {
    res = await apiFetch(`${BASE}/learning/ingest`, {
      method: 'POST',
      body: form,
      signal,
    });
  } catch (err: any) {
    if (err.name === 'AbortError') return;
    onError(err.message || 'Network error');
    return;
  }

  if (!res.ok) {
    onError(`Server error: ${res.status}`);
    return;
  }

  const reader = res.body?.getReader();
  if (!reader) {
    onError('No response stream');
    return;
  }

  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        try {
          const event: SSEEvent = JSON.parse(line.slice(6));
          if (event.stage === 'completed' && event.result) {
            onResult(event.result);
          } else if (event.stage === 'error') {
            onError(event.message || 'Unknown error');
            return;
          } else {
            onStage(event.stage);
          }
        } catch {
          // skip malformed lines
        }
      }
    }
  } catch (err: any) {
    if (err.name === 'AbortError') return;
    onError(err.message || 'Stream read error');
  }
}
