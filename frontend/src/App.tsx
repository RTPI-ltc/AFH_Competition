import { useState, useEffect } from 'react';
import { useApp } from './contexts/AppContext';
import { Sidebar } from './components/Sidebar/Sidebar';
import { ChatArea } from './components/Chat/ChatArea';
import { KnowledgePage } from './components/Knowledge/KnowledgePage';
import { ProductPage } from './components/Knowledge/ProductPage';
import { KnowledgeModal } from './components/Knowledge/KnowledgeModal';
import { SummaryModal } from './components/Knowledge/SummaryModal';
import { PanelLeftOpen } from 'lucide-react';

type Page = 'chat' | 'knowledge' | 'products';

function App() {
  const { state, dispatch } = useApp();
  const [page, setPage] = useState<Page>('chat');
  const [isKnowledgeModalOpen, setIsKnowledgeModalOpen] = useState(false);
  const [summaryTaskId, setSummaryTaskId] = useState<string | null>(null);

  const handleSummarizeProject = async (projectId: string) => {
    // Use project summarize — creates a pseudo-task-id for the modal
    setSummaryTaskId(`__project__${projectId}`);
  };

  return (
    <div className="flex h-screen bg-white overflow-hidden">
      <Sidebar
        onOpenKnowledgeModal={() => setIsKnowledgeModalOpen(true)}
        onSummarize={(taskId) => setSummaryTaskId(taskId)}
        onSummarizeProject={handleSummarizeProject}
        onNavigateToKnowledge={() => setPage(page === 'knowledge' ? 'chat' : 'knowledge')}
        onNavigateToProducts={() => setPage(page === 'products' ? 'chat' : 'products')}
        isKnowledgePage={page === 'knowledge'}
        isProductPage={page === 'products'}
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
        ) : page === 'products' ? (
          <ProductPage onBack={() => setPage('chat')} />
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

      {/* Project summary modal */}
      {summaryTaskId && summaryTaskId.startsWith('__project__') && (
        <ProjectSummaryModal
          isOpen={true}
          projectId={summaryTaskId.replace('__project__', '')}
          onClose={() => setSummaryTaskId(null)}
        />
      )}
    </div>
  );
}

// Inline project summary modal component
function ProjectSummaryModal({ isOpen, projectId, onClose }: {
  isOpen: boolean; projectId: string; onClose: () => void;
}) {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<{
    title: string; rule_points: string[]; recommendations: { item: string; reason: string }[];
    checks: { name: string; status: string }[]; risks: string[];
  } | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (isOpen && projectId) {
      setLoading(true); setError(''); setData(null);
      import('./services/api').then(api => api.summarizeProject(projectId))
        .then(setData).catch(e => setError(e.message || '汇总失败')).finally(() => setLoading(false));
    }
  }, [isOpen, projectId]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-xl mx-4 max-h-[85vh] flex flex-col overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 shrink-0">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-emerald-100 rounded-lg flex items-center justify-center">
              <span className="text-emerald-600 text-sm font-bold">P</span>
            </div>
            <div>
              <h2 className="text-lg font-semibold text-gray-900">项目汇总</h2>
              {data?.title && <p className="text-xs text-gray-400">{data.title}</p>}
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-600">
            <span className="text-lg">&times;</span>
          </button>
        </div>
        <div className="p-6 space-y-4 overflow-y-auto flex-1 text-sm">
          {loading && <p className="text-center text-gray-400 py-8">汇总中...</p>}
          {error && <p className="text-red-600">{error}</p>}
          {data && (
            <>
              {data.recommendations.length > 0 && (
                <div>
                  <h3 className="font-semibold mb-2">推荐商品</h3>
                  {data.recommendations.map((r, i) => (
                    <div key={i} className="flex gap-3 p-3 bg-emerald-50 rounded-xl mb-2">
                      <span className="font-bold text-emerald-600">{i+1}</span>
                      <div><p className="font-medium">{r.item}</p><p className="text-xs text-gray-500">{r.reason}</p></div>
                    </div>
                  ))}
                </div>
              )}
              {data.rule_points.length > 0 && (
                <div>
                  <h3 className="font-semibold mb-2">规则要点</h3>
                  <ul className="list-disc pl-5 space-y-1 text-gray-700">
                    {data.rule_points.map((p, i) => <li key={i}>{p}</li>)}
                  </ul>
                </div>
              )}
              {data.risks.length > 0 && (
                <div>
                  <h3 className="font-semibold mb-2 text-red-600">风险</h3>
                  {data.risks.map((r, i) => <p key={i} className="text-red-700 bg-red-50 p-2 rounded mb-1">{r}</p>)}
                </div>
              )}
              {!data.recommendations.length && !data.rule_points.length && !data.risks.length && (
                <p className="text-gray-400 text-center py-8">暂无汇总数据</p>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
