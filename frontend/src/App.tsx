import { useState, useEffect } from 'react';
import { useApp } from './contexts/AppContext';
import { Sidebar } from './components/Sidebar/Sidebar';
import { ChatArea } from './components/Chat/ChatArea';
import { KnowledgePage } from './components/Knowledge/KnowledgePage';
import { ProductPage } from './components/Knowledge/ProductPage';
import { KnowledgeModal } from './components/Knowledge/KnowledgeModal';
import { SummaryModal } from './components/Knowledge/SummaryModal';
import { AlertTriangle, CheckCircle2, ClipboardList, PackageCheck, PanelLeftOpen, Sparkles, X } from 'lucide-react';
import { summarizeProject, type SummaryListingItem, type SummarySelection } from './services/api';

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
        onNavigateToChat={() => setPage('chat')}
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
  type ProjectSummary = {
    title: string;
    overview?: string;
    rule_points: string[];
    recommendations: { item: string; reason: string }[];
    final_selection?: SummarySelection[];
    selection_reasons?: string[];
    attention_items?: string[];
    confirmed_listing?: SummaryListingItem[];
    checks: { name: string; status: string }[];
    risks: string[];
  };

  const requestToken = isOpen && projectId ? projectId : null;
  const [response, setResponse] = useState<{
    token: string | null;
    data: ProjectSummary | null;
    error: string;
  }>({ token: null, data: null, error: '' });

  useEffect(() => {
    if (!requestToken) return;
    let cancelled = false;
    summarizeProject(requestToken)
      .then((data) => {
        if (!cancelled) setResponse({ token: requestToken, data, error: '' });
      })
      .catch((e) => {
        if (!cancelled) setResponse({ token: requestToken, data: null, error: e.message || '汇总失败' });
      });
    return () => {
      cancelled = true;
    };
  }, [requestToken]);

  const loading = requestToken !== null && response.token !== requestToken;
  const data = response.token === requestToken ? response.data : null;
  const error = response.token === requestToken ? response.error : '';

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-3xl mx-4 max-h-[85vh] flex flex-col overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 shrink-0">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-emerald-100 rounded-lg flex items-center justify-center">
              <PackageCheck size={16} className="text-emerald-600" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-gray-900">项目汇总</h2>
              {data?.title && <p className="text-xs text-gray-400">{data.title}</p>}
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-600">
            <X size={18} />
          </button>
        </div>
        <div className="p-6 space-y-5 overflow-y-auto flex-1 text-sm">
          {loading && <p className="text-center text-gray-400 py-8">汇总中...</p>}
          {error && <p className="text-red-600">{error}</p>}
          {data && (
            <>
              {data.overview && (
                <div className="rounded-xl bg-gray-50 border border-gray-100 px-4 py-3 text-gray-700">
                  {data.overview}
                </div>
              )}
              {(data.final_selection?.length || data.recommendations.length) > 0 && (
                <div>
                  <h3 className="flex items-center gap-2 font-semibold mb-3 text-gray-900">
                    <Sparkles size={16} className="text-emerald-600" />
                    最终选品组合
                  </h3>
                  <div className="grid gap-2 md:grid-cols-2">
                    {(data.final_selection?.length ? data.final_selection : data.recommendations.map((item) => ({
                      sku_id: '',
                      product_name: item.item,
                      status: '待确认',
                      category: '',
                      reason: item.reason,
                    }))).map((item, i) => (
                      <div key={`${item.product_name}-${i}`} className="rounded-xl border border-emerald-100 bg-emerald-50 px-4 py-3">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <p className="font-medium text-gray-900">{item.product_name}</p>
                            <p className="text-xs text-gray-500 mt-1">
                              {[item.sku_id, item.category, item.status].filter(Boolean).join(' · ')}
                            </p>
                          </div>
                          <span className="text-xs font-semibold text-emerald-700">{i + 1}</span>
                        </div>
                        <p className="text-xs text-gray-600 mt-2 leading-relaxed">{item.reason}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {(data.selection_reasons?.length || data.rule_points.length) > 0 && (
                <div>
                  <h3 className="flex items-center gap-2 font-semibold mb-2 text-gray-900">
                    <CheckCircle2 size={16} className="text-blue-600" />
                    最终选品原因
                  </h3>
                  <ul className="space-y-1.5 text-gray-700">
                    {(data.selection_reasons?.length ? data.selection_reasons : data.rule_points).map((p, i) => (
                      <li key={i} className="flex gap-2">
                        <span className="text-blue-500 mt-0.5">•</span>
                        <span>{p}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {data.attention_items && data.attention_items.length > 0 && (
                <div>
                  <h3 className="flex items-center gap-2 font-semibold mb-2 text-amber-700">
                    <AlertTriangle size={16} />
                    注意事项
                  </h3>
                  <div className="space-y-2">
                    {data.attention_items.map((item, i) => (
                      <p key={i} className="rounded-lg bg-amber-50 border border-amber-100 px-3 py-2 text-amber-800">
                        {item}
                      </p>
                    ))}
                  </div>
                </div>
              )}
              {data.confirmed_listing && data.confirmed_listing.length > 0 && (
                <div>
                  <h3 className="flex items-center gap-2 font-semibold mb-2 text-gray-900">
                    <ClipboardList size={16} className="text-indigo-600" />
                    确认后的清单汇总
                  </h3>
                  <div className="overflow-hidden rounded-xl border border-gray-100">
                    {data.confirmed_listing.map((item, i) => (
                      <div key={`${item.product_name}-${i}`} className="grid grid-cols-[1fr_auto] gap-3 px-4 py-3 border-b border-gray-100 last:border-b-0">
                        <div>
                          <p className="font-medium text-gray-800">{item.product_name}</p>
                          <p className="text-xs text-gray-500 mt-1">{[item.sku_id, item.notes].filter(Boolean).join(' · ')}</p>
                        </div>
                        <span className="text-xs text-indigo-700 bg-indigo-50 rounded-full px-2 py-1 h-fit">{item.status}</span>
                      </div>
                    ))}
                  </div>
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
              {!data.recommendations.length && !data.rule_points.length && !data.risks.length && !data.confirmed_listing?.length && (
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
