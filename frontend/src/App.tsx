import { useState } from 'react';
import { useApp } from './contexts/AppContext';
import { Sidebar } from './components/Sidebar/Sidebar';
import { ChatArea } from './components/Chat/ChatArea';
import { KnowledgePage } from './components/Knowledge/KnowledgePage';
import { ApiConfigPage } from './components/Knowledge/ApiConfigPage';
import { KnowledgeModal } from './components/Knowledge/KnowledgeModal';
import { SummaryModal } from './components/Knowledge/SummaryModal';
import { AgentLibraryPage } from './components/AgentLibrary/AgentLibraryPage';
import { PanelLeftOpen } from 'lucide-react';

type Page = 'chat' | 'knowledge' | 'agents' | 'api-config';

function App() {
  const { state, dispatch } = useApp();
  const [page, setPage] = useState<Page>('chat');
  const [isKnowledgeModalOpen, setIsKnowledgeModalOpen] = useState(false);
  const [summaryTaskId, setSummaryTaskId] = useState<string | null>(null);

  return (
    <div className="flex h-screen bg-white overflow-hidden">
      <Sidebar
        onOpenKnowledgeModal={() => setIsKnowledgeModalOpen(true)}
        onSummarize={(taskId) => setSummaryTaskId(taskId)}
        onNavigateToKnowledge={() => setPage(page === 'knowledge' ? 'chat' : 'knowledge')}
        onNavigateToAgents={() => setPage(page === 'agents' ? 'chat' : 'agents')}
        onNavigateToApiConfig={() => setPage(page === 'api-config' ? 'chat' : 'api-config')}
        onNavigateToChat={() => setPage('chat')}
        isKnowledgePage={page === 'knowledge'}
        isAgentPage={page === 'agents'}
        isApiConfigPage={page === 'api-config'}
      />

      <div className="flex-1 flex flex-col min-w-0 relative">
        {!state.isSidebarOpen && (
          <button
            onClick={() => dispatch({ type: 'TOGGLE_SIDEBAR' })}
            className="absolute top-4 left-4 z-10 p-2 rounded-lg bg-white border border-gray-200 shadow-sm hover:bg-gray-50 transition-colors"
          >
            <PanelLeftOpen size={18} className="text-gray-600" />
          </button>
        )}

        {page === 'knowledge' ? (
          <KnowledgePage
            onBack={() => setPage('chat')}
            onImport={() => setIsKnowledgeModalOpen(true)}
          />
        ) : page === 'agents' ? (
          <AgentLibraryPage onBack={() => setPage('chat')} />
        ) : page === 'api-config' ? (
          <ApiConfigPage onBack={() => setPage('chat')} />
        ) : (
          <ChatArea onOpenKnowledgeModal={() => setIsKnowledgeModalOpen(true)} />
        )}
      </div>

      <KnowledgeModal isOpen={isKnowledgeModalOpen} onClose={() => setIsKnowledgeModalOpen(false)} />

      {/* Task summary modal */}
      {summaryTaskId && !summaryTaskId.startsWith('__project__') && (
        <SummaryModal
          isOpen={true}
          taskId={summaryTaskId}
          onClose={() => setSummaryTaskId(null)}
        />
      )}
    </div>
  );
}

export default App;
