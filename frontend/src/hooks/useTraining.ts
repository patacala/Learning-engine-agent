import { useState, useCallback, useRef, useEffect } from 'react';
import type { Agent, TrainingSession, TrainingResult } from '../types/training';
import * as api from '../api/trainingApi';

const STAGE_LABELS: Record<string, string> = {
  transcribing: 'Transcribing audio...',
  extracting: 'Extracting patterns...',
  analyzing: 'Analyzing style & DNA...',
  creating_proposals: 'Creating proposals...',
};

export function useTraining() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(() =>
    localStorage.getItem('training_agent_id'),
  );
  const [sessions, setSessions] = useState<TrainingSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [currentResult, setCurrentResult] = useState<TrainingResult | null>(null);
  const [processingStage, setProcessingStage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const fetchAgents = useCallback(async () => {
    try {
      const data = await api.listAgents();
      setAgents(data);
    } catch (err) {
      console.error('Failed to fetch agents', err);
    }
  }, []);

  const fetchSessions = useCallback(async (agentId: string) => {
    try {
      const data = await api.listSessions(agentId);
      setSessions(data);
    } catch (err) {
      console.error('Failed to fetch sessions', err);
    }
  }, []);

  const selectAgent = useCallback(
    (id: string) => {
      setSelectedAgentId(id);
      localStorage.setItem('training_agent_id', id);
      setActiveSessionId(null);
      setCurrentResult(null);
      setError(null);
      fetchSessions(id);
    },
    [fetchSessions],
  );

  const selectSession = useCallback(async (sessionId: string) => {
    setActiveSessionId(sessionId);
    setProcessingStage(null);
    setError(null);
    try {
      const proposals = await api.listProposals(sessionId);
      setCurrentResult({
        session_id: sessionId,
        source_label: '',
        transcript: '',
        patterns_extracted: proposals.length,
        proposals,
      });
    } catch (err: any) {
      setError(err.message);
      setCurrentResult(null);
    }
  }, []);

  const openDraftSession = useCallback(
    async (sessionId: string) => {
      // A handoff creates the draft outside this hook, so refresh the sidebar
      // before selecting it. Selecting the session also gives ChatArea the
      // empty-result state it needs to render the "Procesar borrador" action.
      if (selectedAgentId) {
        await fetchSessions(selectedAgentId);
      }
      await selectSession(sessionId);
    },
    [selectedAgentId, fetchSessions, selectSession],
  );

  const extractSession = useCallback(
    async (sessionId: string) => {
      setError(null);
      setProcessingStage('Extracting patterns...');
      try {
        const result = await api.extractSession(sessionId);
        setCurrentResult(result);
        setActiveSessionId(sessionId);
        if (selectedAgentId) fetchSessions(selectedAgentId);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setProcessingStage(null);
      }
    },
    [selectedAgentId, fetchSessions],
  );

  const startNewSession = useCallback(() => {
    setActiveSessionId(null);
    setCurrentResult(null);
    setError(null);
    setProcessingStage(null);
  }, []);

  const deleteSession = useCallback(async (sessionId: string) => {
    try {
      await api.deleteSession(sessionId);
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
      if (activeSessionId === sessionId) {
        setActiveSessionId(null);
        setCurrentResult(null);
      }
    } catch (err: any) {
      console.error('Delete failed', err);
    }
  }, [activeSessionId]);

  const submitTranscript = useCallback(
    async (transcript: string, audio?: File) => {
      if (!selectedAgentId) return;

      // Abort previous
      if (abortRef.current) abortRef.current.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      setIsLoading(true);
      setProcessingStage('Extracting patterns...');
      setError(null);

      await api.ingestTranscript(
        {
          agentVersionId: selectedAgentId,
          transcript: transcript || undefined,
          audio,
          sessionId: activeSessionId || undefined,
        },
        (stage) => {
          const label = STAGE_LABELS[stage] || stage;
          setProcessingStage(label);
        },
        (result) => {
          setIsLoading(false);
          setProcessingStage(null);
          abortRef.current = null;
          setCurrentResult(result);
          setActiveSessionId(result.session_id);
          fetchSessions(selectedAgentId);
        },
        (message) => {
          setIsLoading(false);
          setProcessingStage(null);
          abortRef.current = null;
          setError(message);
        },
        controller.signal,
      );
    },
    [selectedAgentId, activeSessionId, fetchSessions],
  );

  const approveProposal = useCallback(async (proposalId: string) => {
    try {
      const updated = await api.updateProposal(proposalId, 'approved');
      setCurrentResult((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          proposals: prev.proposals.map((p) =>
            p.id === proposalId ? { ...p, ...updated } : p,
          ),
        };
      });
    } catch (err: any) {
      console.error('Approve failed', err);
    }
  }, []);

  const rejectProposal = useCallback(async (proposalId: string) => {
    try {
      const updated = await api.updateProposal(proposalId, 'rejected');
      setCurrentResult((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          proposals: prev.proposals.map((p) =>
            p.id === proposalId ? { ...p, ...updated } : p,
          ),
        };
      });
    } catch (err: any) {
      console.error('Reject failed', err);
    }
  }, []);

  const editAndApprove = useCallback(async (proposalId: string, content: string, title?: string) => {
    try {
      const updated = await api.updateProposal(proposalId, 'approved', { content, title });
      setCurrentResult((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          proposals: prev.proposals.map((p) =>
            p.id === proposalId ? { ...p, ...updated } : p,
          ),
        };
      });
    } catch (err: any) {
      console.error('Edit and approve failed', err);
    }
  }, []);

  const approveAll = useCallback(async () => {
    if (!currentResult) return;
    const pendingIds = currentResult.proposals
      .filter((p) => p.status === 'pending')
      .map((p) => p.id);
    if (pendingIds.length === 0) return;

    // Optimistic update
    setCurrentResult((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        proposals: prev.proposals.map((p) =>
          p.status === 'pending' ? { ...p, status: 'approved' } : p,
        ),
      };
    });

    try {
      const results = await api.batchUpdateProposals(pendingIds, 'approved');
      setCurrentResult((current) => {
        if (!current) return current;
        const updatedMap = new Map(results.map((r) => [r.id, r]));
        return {
          ...current,
          proposals: current.proposals.map((p) =>
            updatedMap.has(p.id) ? { ...p, ...updatedMap.get(p.id)! } : p,
          ),
        };
      });
    } catch (err) {
      console.error('Batch approve failed', err);
    }
  }, [currentResult]);

  useEffect(() => {
    fetchAgents();
  }, [fetchAgents]);

  useEffect(() => {
    if (selectedAgentId) fetchSessions(selectedAgentId);
  }, [selectedAgentId, fetchSessions]);

  return {
    agents,
    selectedAgentId,
    sessions,
    activeSessionId,
    currentResult,
    processingStage,
    error,
    isLoading,
    selectAgent,
    selectSession,
    openDraftSession,
    extractSession,
    startNewSession,
    deleteSession,
    submitTranscript,
    approveProposal,
    rejectProposal,
    editAndApprove,
    approveAll,
  };
}
