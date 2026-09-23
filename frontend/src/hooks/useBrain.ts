import { useState, useCallback } from 'react';
import type { AgentBrain } from '../types/training';
import { getAgentBrain } from '../api/trainingApi';

export function useBrain() {
  const [brain, setBrain] = useState<AgentBrain | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchBrain = useCallback(async (agentVersionId: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await getAgentBrain(agentVersionId);
      setBrain(data);
    } catch (err: any) {
      setError(err.message);
      setBrain(null);
    } finally {
      setLoading(false);
    }
  }, []);

  const clearBrain = useCallback(() => {
    setBrain(null);
    setError(null);
  }, []);

  return { brain, loading, error, fetchBrain, clearBrain };
}
