import { useCallback, useEffect, useState } from 'react';
import type { Scenario, TemporaryDocument, TestChatMessage } from '../types/testing';
import type { ScenarioTemplate } from '../constants/testingTemplates';
import { docId, instantiateTemplate } from '../constants/testingTemplates';
import * as api from '../api/testingApi';

export function useTesting(selectedAgentId: string | null) {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [selectedScenarioId, setSelectedScenarioId] = useState<string | null>(null);

  // Active (possibly unsaved) context
  const [scenarioName, setScenarioName] = useState('');
  const [companyName, setCompanyName] = useState('');
  const [documents, setDocuments] = useState<TemporaryDocument[]>([]);
  const [quickFacts, setQuickFacts] = useState<Record<string, string>>({});

  const [messages, setMessages] = useState<TestChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchScenarios = useCallback(async (agentId: string) => {
    try {
      const data = await api.listScenarios(agentId);
      setScenarios(data);
    } catch (err) {
      console.error('Failed to fetch scenarios', err);
    }
  }, []);

  useEffect(() => {
    if (selectedAgentId) {
      void fetchScenarios(selectedAgentId);
    } else {
      setScenarios([]);
    }
  }, [selectedAgentId, fetchScenarios]);

  const newScenario = useCallback(() => {
    setSelectedScenarioId(null);
    setScenarioName('');
    setCompanyName('');
    setDocuments([]);
    setQuickFacts({});
    setMessages([]);
    setError(null);
  }, []);

  const loadScenario = useCallback((scenario: Scenario) => {
    setSelectedScenarioId(scenario.id);
    setScenarioName(scenario.name);
    setCompanyName(scenario.company_name);
    setDocuments(scenario.documents);
    setQuickFacts(scenario.quick_facts);
    setMessages([]);
    setError(null);
  }, []);

  const applyTemplate = useCallback((tmpl: ScenarioTemplate) => {
    setSelectedScenarioId(null);
    setScenarioName(tmpl.label);
    setCompanyName(tmpl.company_name);
    setDocuments(instantiateTemplate(tmpl));
    setQuickFacts({ ...tmpl.quick_facts });
    setMessages([]);
    setError(null);
  }, []);

  const addDocument = useCallback(() => {
    setDocuments((prev) => [
      { id: docId(), title: '', content: '', category: 'general' },
      ...prev,
    ]);
  }, []);

  const updateDocument = useCallback((id: string, patch: Partial<TemporaryDocument>) => {
    setDocuments((prev) => prev.map((d) => (d.id === id ? { ...d, ...patch } : d)));
  }, []);

  const removeDocument = useCallback((id: string) => {
    setDocuments((prev) => prev.filter((d) => d.id !== id));
  }, []);

  const setQuickFact = useCallback((key: string, value: string) => {
    setQuickFacts((prev) => ({ ...prev, [key]: value }));
  }, []);

  const removeQuickFact = useCallback((key: string) => {
    setQuickFacts((prev) => {
      const next = { ...prev };
      delete next[key];
      return next;
    });
  }, []);

  const saveScenario = useCallback(async (): Promise<boolean> => {
    if (!selectedAgentId) return false;
    const payload = {
      name: scenarioName || companyName || 'Escenario sin nombre',
      company_name: companyName,
      agent_version_id: selectedAgentId,
      documents,
      quick_facts: quickFacts,
    };
    try {
      if (selectedScenarioId) {
        const updated = await api.updateScenario(selectedScenarioId, payload);
        setScenarios((prev) => prev.map((s) => (s.id === updated.id ? updated : s)));
      } else {
        const created = await api.createScenario(payload);
        setSelectedScenarioId(created.id);
        setScenarios((prev) => [created, ...prev]);
      }
      return true;
    } catch (err: any) {
      setError(err.message || 'No se pudo guardar el escenario');
      return false;
    }
  }, [selectedAgentId, selectedScenarioId, scenarioName, companyName, documents, quickFacts]);

  const removeScenario = useCallback(
    async (id: string) => {
      try {
        await api.deleteScenario(id);
        setScenarios((prev) => prev.filter((s) => s.id !== id));
        if (selectedScenarioId === id) newScenario();
      } catch (err) {
        console.error('Delete scenario failed', err);
      }
    },
    [selectedScenarioId, newScenario],
  );

  const sendMessage = useCallback(
    async (message: string) => {
      if (!selectedAgentId || !message.trim()) return;

      const history = messages.map((m) => ({ role: m.role, content: m.content }));
      setMessages((prev) => [...prev, { role: 'user', content: message }]);
      setIsLoading(true);
      setError(null);

      try {
        const res = await api.sendTestMessage(selectedAgentId, {
          message,
          history,
          company_name: companyName,
          documents,
          quick_facts: quickFacts,
        });
        setMessages((prev) => [
          ...prev,
          { role: 'assistant', content: res.response, debug: res.debug },
        ]);
      } catch (err: any) {
        setError(err.message || 'Failed to run the test conversation');
      } finally {
        setIsLoading(false);
      }
    },
    [selectedAgentId, messages, companyName, documents, quickFacts],
  );

  const clearConversation = useCallback(() => {
    setMessages([]);
    setError(null);
  }, []);

  const sendToTraining = useCallback(async () => {
    if (!selectedAgentId || messages.length === 0) return null;
    const transcript = messages
      .map((m) => `${m.role === 'user' ? 'Cliente' : 'Agente'}: ${m.content}`)
      .join('\n');
    const label = `Playground: ${companyName || scenarioName || 'prueba'}`;
    try {
      return await api.handoffToTraining({
        agent_version_id: selectedAgentId,
        source_label: label,
        transcript,
      });
    } catch (err: any) {
      setError(err.message || 'No se pudo enviar a Training');
      return null;
    }
  }, [selectedAgentId, messages, companyName, scenarioName]);

  return {
    scenarios,
    selectedScenarioId,
    scenarioName,
    companyName,
    documents,
    quickFacts,
    messages,
    isLoading,
    error,
    setScenarioName,
    setCompanyName,
    newScenario,
    loadScenario,
    applyTemplate,
    addDocument,
    updateDocument,
    removeDocument,
    setQuickFact,
    removeQuickFact,
    saveScenario,
    removeScenario,
    sendMessage,
    clearConversation,
    sendToTraining,
  };
}
