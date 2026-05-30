import { useApp } from '../../contexts/AppContext';
import { useEffect } from 'react';
import { NewTaskButton } from './NewTaskButton';
import { ProjectList } from './ProjectList';
import { HistoryList } from './HistoryList';
import { AgentSection } from './AgentSection';
import { BookOpen, Upload, ChevronLeft, Bot, KeyRound, ShieldCheck } from 'lucide-react';
import { useState } from 'react';

interface SidebarProps {
  onOpenKnowledgeModal: () => void;
  onSummarize: (taskId: string) => void;
  onNavigateToKnowledge: () => void;
  onNavigateToAgents: () => void;
  onNavigateToApiConfig: () => void;
  onNavigateToChat: () => void;
  isKnowledgePage: boolean;
  isAgentPage: boolean;
  isApiConfigPage: boolean;
}

export function Sidebar({
  onOpenKnowledgeModal,
  onSummarize,
  onNavigateToKnowledge,
  onNavigateToAgents,
  onNavigateToApiConfig,
  onNavigateToChat,
  isKnowledgePage,
  isAgentPage,
  isApiConfigPage,
}: SidebarProps) {
  const { state, dispatch, loadHistory, loadKnowledge, loadProjects, loadAgents } = useApp();
  const [showHistory, setShowHistory] = useState(true);

  useEffect(() => {
    loadProjects();
    loadHistory();
    loadKnowledge();
    loadAgents();
  }, [loadAgents, loadHistory, loadKnowledge, loadProjects]);

  return (
    <aside
      className={`${
        state.isSidebarOpen ? 'w-72' : 'w-0'
      } bg-gray-50 border-r border-gray-200 flex flex-col h-full transition-all duration-300 overflow-hidden`}
    >
      {state.isSidebarOpen && (
        <>
          {/* Header */}
          <div className="p-4 border-b border-gray-200">
            <div className="flex items-center gap-2 mb-3">
              <div className="w-8 h-8 bg-indigo-600 rounded-lg flex items-center justify-center">
                <Bot size={18} className="text-white" />
              </div>
              <h1 className="text-lg font-semibold text-gray-900">知识库 Agent</h1>
            </div>
            <NewTaskButton onTaskStarted={onNavigateToChat} />
          </div>

          {/* Scrollable content */}
          <div className="flex-1 overflow-y-auto py-2 space-y-4">
            {/* Knowledge btn + Import */}
            <div className="px-2 space-y-1">
              <button
                onClick={onNavigateToKnowledge}
                className={`flex items-center gap-2 w-full px-3 py-2 text-sm rounded-lg transition-colors ${
                  isKnowledgePage
                    ? 'bg-indigo-50 text-indigo-700 font-medium'
                    : 'text-gray-600 hover:bg-gray-100'
                }`}
              >
                <BookOpen size={16} />
                <span className="flex-1 text-left">知识库</span>
                <span className="text-[10px] text-gray-400">{state.knowledgeList.length}</span>
              </button>
              <button
                onClick={onOpenKnowledgeModal}
                className="flex items-center gap-2 w-full px-3 py-2 text-sm text-gray-500 hover:bg-gray-200 rounded-lg transition-colors"
              >
                <Upload size={16} />
                <span>导入知识库</span>
              </button>
            </div>

            {/* Agent library + API config */}
            <div className="px-2 space-y-1">
              <button
                onClick={onNavigateToAgents}
                className={`flex items-center gap-2 w-full px-3 py-2 text-sm rounded-lg transition-colors ${
                  isAgentPage
                    ? 'bg-blue-50 text-blue-700 font-medium'
                    : 'text-gray-600 hover:bg-gray-100'
                }`}
              >
                <ShieldCheck size={16} />
                <span className="flex-1 text-left">Agent 库</span>
              </button>
              <button
                onClick={onNavigateToApiConfig}
                className={`flex items-center gap-2 w-full px-3 py-2 text-sm rounded-lg transition-colors ${
                  isApiConfigPage
                    ? 'bg-violet-50 text-violet-700 font-medium'
                    : 'text-gray-600 hover:bg-gray-100'
                }`}
              >
                <KeyRound size={16} />
                <span className="flex-1 text-left">API 配置</span>
              </button>
            </div>

            {/* Divider */}
            <div className="border-t border-gray-200 mx-3" />

            <AgentSection />

            <div className="border-t border-gray-200 mx-3" />

            {/* Project list */}
            <ProjectList />

            {/* Divider */}
            <div className="border-t border-gray-200 mx-3" />

            {/* History section */}
            <div>
              <button
                onClick={() => setShowHistory(!showHistory)}
                className="flex items-center gap-2 w-full px-3 py-2 text-sm font-medium text-gray-600"
              >
                <span className="flex-1 text-left text-xs uppercase tracking-wider text-gray-400">
                  历史记录
                </span>
                <span className="text-[10px] text-gray-400">
                  {state.history.length}
                </span>
              </button>
              {showHistory && <HistoryList onSummarize={onSummarize} />}
            </div>
          </div>

          {/* Footer */}
          <div className="p-3 border-t border-gray-200">
            <button
              onClick={() => dispatch({ type: 'TOGGLE_SIDEBAR' })}
              className="flex items-center gap-2 text-xs text-gray-400 hover:text-gray-600 transition-colors"
            >
              <ChevronLeft size={14} />
              <span>收起侧边栏</span>
            </button>
          </div>
        </>
      )}
    </aside>
  );
}
