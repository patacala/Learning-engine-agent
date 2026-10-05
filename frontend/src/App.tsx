import { useState, useEffect, useCallback } from 'react';
import { useAuth } from './hooks/useAuth';
import { useTraining } from './hooks/useTraining';
import { useBrain } from './hooks/useBrain';
import { ChatLayout } from './components/layout/ChatLayout';
import { LoginScreen } from './components/auth/LoginScreen';
import { SessionSidebar, type SidebarView } from './components/sidebar/SessionSidebar';
import { ChatArea } from './components/chat/ChatArea';
import { BrainDashboard } from './components/brain/BrainDashboard';
import { TestPlayground } from './components/testing/TestPlayground';

function App() {
  const { status: authStatus, loginError, submitLogin, signOut } = useAuth();
  const {
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
  } = useTraining();

  const [view, setView] = useState<SidebarView>('training');
  const { brain, loading: brainLoading, error: brainError, fetchBrain, clearBrain } = useBrain();

  const refreshBrain = useCallback(() => {
    if (selectedAgentId) {
      void fetchBrain(selectedAgentId);
    }
  }, [selectedAgentId, fetchBrain]);

  useEffect(() => {
    if (view === 'brain' && selectedAgentId) {
      void fetchBrain(selectedAgentId);
    }
  }, [view, selectedAgentId, fetchBrain]);

  const handleSelectAgent = useCallback(
    (id: string) => {
      clearBrain();
      selectAgent(id);
    },
    [clearBrain, selectAgent],
  );

  const handleTestHandoff = useCallback(
    async (sessionId: string) => {
      await openDraftSession(sessionId);
      setView('training');
    },
    [openDraftSession],
  );

  const handleApprove = useCallback(
    async (id: string) => {
      await approveProposal(id);
      refreshBrain();
    },
    [approveProposal, refreshBrain],
  );

  const handleReject = useCallback(
    async (id: string) => {
      await rejectProposal(id);
      refreshBrain();
    },
    [rejectProposal, refreshBrain],
  );

  const handleEditAndApprove = useCallback(
    async (id: string, content: string, title?: string) => {
      await editAndApprove(id, content, title);
      refreshBrain();
    },
    [editAndApprove, refreshBrain],
  );

  const handleApproveAll = useCallback(async () => {
    await approveAll();
    refreshBrain();
  }, [approveAll, refreshBrain]);

  const content = view === 'brain' ? (
    <BrainDashboard
      brain={brain}
      loading={brainLoading}
      error={brainError}
      agentVersionId={selectedAgentId}
    />
  ) : view === 'testing' ? (
    <TestPlayground selectedAgentId={selectedAgentId} onHandoffSuccess={handleTestHandoff} />
  ) : (
    <ChatArea
      currentResult={currentResult}
      processingStage={processingStage}
      error={error}
      isLoading={isLoading}
      hasAgent={!!selectedAgentId}
      activeSessionId={activeSessionId}
      onApprove={handleApprove}
      onReject={handleReject}
      onEditAndApprove={handleEditAndApprove}
      onApproveAll={handleApproveAll}
      onExtractDraft={extractSession}
      onSubmit={submitTranscript}
    />
  );

  if (authStatus !== 'authenticated') {
    return authStatus === 'checking' ? null : (
      <LoginScreen error={loginError} onSubmit={submitLogin} />
    );
  }

  return (
    <div className="relative h-screen">
      <button
        onClick={() => void signOut()}
        className="absolute top-2 right-2 z-10 text-xs text-gray-400 hover:text-gray-700 px-2 py-1"
      >
        Sign out
      </button>
      <ChatLayout
        sidebar={
          <SessionSidebar
            agents={agents}
            selectedAgentId={selectedAgentId}
            sessions={sessions}
            activeSessionId={activeSessionId}
            currentView={view}
            onSelectAgent={handleSelectAgent}
            onSelectSession={selectSession}
            onDeleteSession={deleteSession}
            onNewSession={startNewSession}
            onChangeView={setView}
          />
        }
        content={content}
      />
    </div>
  );
}

export default App;
