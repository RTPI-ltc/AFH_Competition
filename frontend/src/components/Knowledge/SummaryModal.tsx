import { useState, useEffect } from 'react';
import { X, FileBarChart, AlertTriangle, Loader2, Bot, Quote, MessageCircleQuestion } from 'lucide-react';
import { summarizeTask } from '../../services/api';

interface SummaryModalProps {
  isOpen: boolean;
  taskId: string | null;
  onClose: () => void;
}

type RagSource = {
  source_file: string;
  kb_id: string;
  snippet: string;
};

type SummaryData = {
  title: string;
  overview?: string;
  agents?: string[];
  evidence_notes: string[];
  follow_up_questions: string[];
  rag_sources: RagSource[];
};

export function SummaryModal({ isOpen, taskId, onClose }: SummaryModalProps) {
  const requestToken = isOpen && taskId ? taskId : null;
  const [response, setResponse] = useState<{
    token: string | null;
    data: SummaryData | null;
    error: string;
  }>({ token: null, data: null, error: '' });

  useEffect(() => {
    if (!requestToken) return;
    let cancelled = false;
    summarizeTask(requestToken)
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
  const hasContent = data
    && ((data.agents?.length || 0) > 0
      || data.evidence_notes.length > 0
      || data.follow_up_questions.length > 0
      || data.rag_sources.length > 0);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-xl mx-4 max-h-[85vh] flex flex-col overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 shrink-0">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-emerald-100 rounded-lg flex items-center justify-center">
              <FileBarChart size={16} className="text-emerald-600" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-gray-900">对话沉淀</h2>
              {data?.title && <p className="text-xs text-gray-400">{data.title}</p>}
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors">
            <X size={18} />
          </button>
        </div>

        <div className="p-6 space-y-5 overflow-y-auto flex-1">
          {loading && (
            <div className="flex items-center justify-center py-12">
              <Loader2 size={28} className="animate-spin text-indigo-500" />
            </div>
          )}

          {error && (
            <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 rounded-xl">
              <AlertTriangle size={14} className="text-red-500 shrink-0" />
              <p className="text-sm text-red-700">{error}</p>
            </div>
          )}

          {data && (
            <>
              {data.overview && <p className="text-sm leading-relaxed text-gray-600">{data.overview}</p>}

              {(data.agents?.length || 0) > 0 && (
                <section>
                  <h3 className="flex items-center gap-2 text-sm font-semibold text-gray-800 mb-3">
                    <Bot size={16} className="text-indigo-600" />
                    使用过的 Agent
                  </h3>
                  <div className="flex flex-wrap gap-2">
                    {data.agents?.map((agent) => (
                      <span key={agent} className="rounded-md bg-indigo-50 px-2 py-1 text-xs text-indigo-700">
                        {agent}
                      </span>
                    ))}
                  </div>
                </section>
              )}

              {data.evidence_notes.length > 0 && (
                <section>
                  <h3 className="flex items-center gap-2 text-sm font-semibold text-gray-800 mb-3">
                    <Quote size={16} className="text-emerald-600" />
                    证据边界
                  </h3>
                  <div className="space-y-2">
                    {data.evidence_notes.map((note, i) => (
                      <p key={i} className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
                        {note}
                      </p>
                    ))}
                  </div>
                </section>
              )}

              {data.follow_up_questions.length > 0 && (
                <section>
                  <h3 className="flex items-center gap-2 text-sm font-semibold text-gray-800 mb-3">
                    <MessageCircleQuestion size={16} className="text-amber-600" />
                    待补充问题
                  </h3>
                  <div className="space-y-2">
                    {data.follow_up_questions.map((question, i) => (
                      <p key={i} className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">
                        {question}
                      </p>
                    ))}
                  </div>
                </section>
              )}

              {data.rag_sources.length > 0 && (
                <section>
                  <h3 className="flex items-center gap-2 text-sm font-semibold text-gray-800 mb-3">
                    <Quote size={16} className="text-blue-600" />
                    引用片段
                  </h3>
                  <div className="space-y-2">
                    {data.rag_sources.map((source, i) => (
                      <div key={`${source.kb_id}-${source.source_file}-${i}`} className="rounded-lg border border-blue-100 bg-blue-50 px-3 py-2">
                        <p className="text-xs font-medium text-blue-700">{source.source_file || source.kb_id}</p>
                        {source.snippet && <p className="mt-1 text-xs leading-relaxed text-gray-600">{source.snippet}</p>}
                      </div>
                    ))}
                  </div>
                </section>
              )}

              {!hasContent && (
                <p className="text-center text-gray-400 text-sm py-8">暂无可沉淀的 Agent 证据，请先进行对话</p>
              )}
            </>
          )}
        </div>

        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-100 bg-gray-50 shrink-0">
          <button onClick={onClose} className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800 transition-colors">关闭</button>
        </div>
      </div>
    </div>
  );
}
