import { useState } from 'react';
import { useApp } from './contexts/AppContext';
import { Sidebar } from './components/Sidebar/Sidebar';
import { ChatArea } from './components/Chat/ChatArea';
import { KnowledgeModal } from './components/Knowledge/KnowledgeModal';
import { SummaryModal } from './components/Knowledge/SummaryModal';
import { PanelLeftOpen } from 'lucide-react';

function App() {
  const { state, dispatch } = useApp();
  const [isKnowledgeModalOpen, setIsKnowledgeModalOpen] = useState(false);
  const [summaryTaskId, setSummaryTaskId] = useState<string | null>(null);

  return (
    <div className="flex h-screen bg-white overflow-hidden">
      {/* Sidebar */}
      <Sidebar
        onOpenKnowledgeModal={() => setIsKnowledgeModalOpen(true)}
        onSummarize={(taskId) => setSummaryTaskId(taskId)}
      />

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0 relative">
        {!state.isSidebarOpen && (
          <button
            onClick={() => dispatch({ type: 'TOGGLE_SIDEBAR' })}
            className="absolute top-4 left-4 z-10 p-2 rounded-lg bg-white border border-gray-200 shadow-sm hover:bg-gray-50 transition-colors"
          >
            <PanelLeftOpen size={18} className="text-gray-600" />
          </button>
        )}

        <ChatArea onOpenKnowledgeModal={() => setIsKnowledgeModalOpen(true)} />
      </div>

      <KnowledgeModal isOpen={isKnowledgeModalOpen} onClose={() => setIsKnowledgeModalOpen(false)} />
      <SummaryModal isOpen={!!summaryTaskId} taskId={summaryTaskId} onClose={() => setSummaryTaskId(null)} />
    </div>
  );
}

export default App;
