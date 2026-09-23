import { useState } from 'react';
import { useTesting } from '../../hooks/useTesting';
import { ContextInjector } from './ContextInjector';
import { TestChatPanel } from './TestChatPanel';

interface Props {
  selectedAgentId: string | null;
  onHandoffSuccess: (sessionId: string) => Promise<void> | void;
}

export function TestPlayground({ selectedAgentId, onHandoffSuccess }: Props) {
  const t = useTesting(selectedAgentId);
  const [notice, setNotice] = useState<string | null>(null);
  const [isSendingToTraining, setIsSendingToTraining] = useState(false);

  const handleSendToTraining = async () => {
    setIsSendingToTraining(true);
    try {
      const result = await t.sendToTraining();
      if (result) {
        await onHandoffSuccess(result.session_id);
      }
    } finally {
      setIsSendingToTraining(false);
    }
  };

  const handleSaveScenario = async () => {
    const wasUpdate = !!t.selectedScenarioId;
    const ok = await t.saveScenario();
    if (ok) {
      setNotice(wasUpdate ? 'Scenario updated ✓' : 'Scenario saved ✓');
      setTimeout(() => setNotice(null), 4000);
    }
  };

  return (
    <div className="flex-1 flex min-w-0 overflow-hidden relative">
      {notice && (
        <div className="absolute top-3 left-1/2 -translate-x-1/2 z-10 bg-[#0d0d0d] text-white text-[12px] px-3 py-1.5 rounded-lg shadow-lg">
          {notice}
        </div>
      )}

      <TestChatPanel
        messages={t.messages}
        isLoading={t.isLoading}
        error={t.error}
        hasAgent={!!selectedAgentId}
        companyName={t.companyName}
        onSend={t.sendMessage}
        onClear={t.clearConversation}
        onSendToTraining={handleSendToTraining}
        isSendingToTraining={isSendingToTraining}
      />

      {selectedAgentId && (
        <ContextInjector
          scenarios={t.scenarios}
          selectedScenarioId={t.selectedScenarioId}
          scenarioName={t.scenarioName}
          companyName={t.companyName}
          documents={t.documents}
          quickFacts={t.quickFacts}
          onScenarioNameChange={t.setScenarioName}
          onCompanyNameChange={t.setCompanyName}
          onNewScenario={t.newScenario}
          onLoadScenario={t.loadScenario}
          onDeleteScenario={t.removeScenario}
          onApplyTemplate={t.applyTemplate}
          onAddDocument={t.addDocument}
          onUpdateDocument={t.updateDocument}
          onRemoveDocument={t.removeDocument}
          onSetQuickFact={t.setQuickFact}
          onRemoveQuickFact={t.removeQuickFact}
          onSaveScenario={handleSaveScenario}
        />
      )}
    </div>
  );
}
