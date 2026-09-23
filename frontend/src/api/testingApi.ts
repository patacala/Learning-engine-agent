import type {
  Scenario,
  TemporaryDocument,
  TestMessageResponse,
  TestTurn,
} from '../types/testing';
import { apiFetch } from './http';

const BASE = '/api/v1';

export async function listScenarios(agentVersionId: string): Promise<Scenario[]> {
  const res = await apiFetch(`${BASE}/testing/scenarios?agent_version_id=${agentVersionId}`);
  if (!res.ok) throw new Error('Failed to fetch scenarios');
  return res.json();
}

export async function createScenario(payload: {
  name: string;
  company_name: string;
  agent_version_id: string;
  documents: TemporaryDocument[];
  quick_facts: Record<string, string>;
}): Promise<Scenario> {
  const res = await apiFetch(`${BASE}/testing/scenarios`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error('Failed to create scenario');
  return res.json();
}

export async function updateScenario(
  scenarioId: string,
  payload: {
    name: string;
    company_name: string;
    agent_version_id: string;
    documents: TemporaryDocument[];
    quick_facts: Record<string, string>;
  },
): Promise<Scenario> {
  const res = await apiFetch(`${BASE}/testing/scenarios/${scenarioId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error('Failed to update scenario');
  return res.json();
}

export async function deleteScenario(scenarioId: string): Promise<void> {
  const res = await apiFetch(`${BASE}/testing/scenarios/${scenarioId}`, { method: 'DELETE' });
  if (!res.ok) throw new Error('Failed to delete scenario');
}

export async function sendTestMessage(
  agentVersionId: string,
  payload: {
    message: string;
    history: TestTurn[];
    company_name: string;
    documents: TemporaryDocument[];
    quick_facts: Record<string, string>;
  },
): Promise<TestMessageResponse> {
  const res = await apiFetch(`${BASE}/agents/${agentVersionId}/test-conversation`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error('Failed to run test conversation');
  return res.json();
}

export async function handoffToTraining(payload: {
  agent_version_id: string;
  source_label: string;
  transcript: string;
}): Promise<{ session_id: string; status: string }> {
  const res = await apiFetch(`${BASE}/testing/handoff`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error('Failed to create training draft');
  return res.json();
}
