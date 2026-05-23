import { useState, useEffect } from 'react';
import { X, FileBarChart, CheckCircle2, AlertTriangle, Lightbulb, Loader2, Package } from 'lucide-react';
import { summarizeTask } from '../../services/api';

interface SummaryModalProps {
  isOpen: boolean;
  taskId: string | null;
  onClose: () => void;
}

export function SummaryModal({ isOpen, taskId, onClose }: SummaryModalProps) {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<{
    title: string;
    rule_points: string[];
    recommendations: { item: string; reason: string }[];
    checks: { name: string; status: string }[];
    risks: string[];
  } | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (isOpen && taskId) {
      setLoading(true);
      setError('');
      setData(null);
      summarizeTask(taskId)
        .then(setData)
        .catch((e) => setError(e.message || '汇总失败'))
        .finally(() => setLoading(false));
    }
  }, [isOpen, taskId]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-xl mx-4 max-h-[85vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 shrink-0">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-emerald-100 rounded-lg flex items-center justify-center">
              <FileBarChart size={16} className="text-emerald-600" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-gray-900">任务汇总</h2>
              {data?.title && <p className="text-xs text-gray-400">{data.title}</p>}
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors">
            <X size={18} />
          </button>
        </div>

        {/* Body */}
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
              {/* Recommendations */}
              {data.recommendations.length > 0 && (
                <div>
                  <h3 className="flex items-center gap-2 text-sm font-semibold text-gray-800 mb-3">
                    <Package size={16} className="text-emerald-600" />
                    推荐商品/品类
                  </h3>
                  <div className="space-y-2">
                    {data.recommendations.map((r, i) => (
                      <div key={i} className="flex items-start gap-3 p-3 bg-emerald-50 border border-emerald-200 rounded-xl">
                        <div className="w-8 h-8 bg-emerald-100 rounded-lg flex items-center justify-center shrink-0">
                          <span className="text-xs font-bold text-emerald-700">{i + 1}</span>
                        </div>
                        <div>
                          <p className="text-sm font-medium text-gray-800">{r.item}</p>
                          <p className="text-xs text-gray-500 mt-0.5">{r.reason}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Rule points */}
              {data.rule_points.length > 0 && (
                <div>
                  <h3 className="flex items-center gap-2 text-sm font-semibold text-gray-800 mb-3">
                    <Lightbulb size={16} className="text-amber-600" />
                    规则要点
                  </h3>
                  <div className="space-y-1.5">
                    {data.rule_points.map((p, i) => (
                      <div key={i} className="flex items-start gap-2 text-sm text-gray-700 pl-1">
                        <span className="text-amber-500 font-bold mt-0.5">•</span>
                        <span>{p}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Checks */}
              {data.checks.length > 0 && (
                <div>
                  <h3 className="flex items-center gap-2 text-sm font-semibold text-gray-800 mb-3">
                    <CheckCircle2 size={16} className="text-blue-600" />
                    检查项状态
                  </h3>
                  <div className="space-y-1.5">
                    {data.checks.map((c, i) => (
                      <div key={i} className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm ${
                        c.status === '通过' ? 'bg-green-50 text-green-700' : 'bg-amber-50 text-amber-700'
                      }`}>
                        <span className={c.status === '通过' ? 'text-green-500' : 'text-amber-500'}>
                          {c.status === '通过' ? '✓' : '!'}
                        </span>
                        <span>{c.name}</span>
                        <span className="text-[10px] ml-auto opacity-70">{c.status}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Risks */}
              {data.risks.length > 0 && (
                <div>
                  <h3 className="flex items-center gap-2 text-sm font-semibold text-gray-800 mb-3">
                    <AlertTriangle size={16} className="text-red-600" />
                    风险提示
                  </h3>
                  <div className="space-y-1.5">
                    {data.risks.map((r, i) => (
                      <div key={i} className="flex items-start gap-2 text-sm text-red-700 bg-red-50 px-3 py-2 rounded-lg">
                        <span className="text-red-500 mt-0.5">⚠</span>
                        <span>{r}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Empty state */}
              {!data.recommendations.length && !data.rule_points.length && !data.checks.length && !data.risks.length && (
                <p className="text-center text-gray-400 text-sm py-8">暂无汇总数据，请先进行对话</p>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-100 bg-gray-50 shrink-0">
          <button onClick={onClose} className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800 transition-colors">关闭</button>
        </div>
      </div>
    </div>
  );
}
