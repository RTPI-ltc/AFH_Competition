import { FileBarChart, Package } from 'lucide-react';
import type { TaskSummary } from '../../types';

interface TaskSummaryCardProps {
  summary: TaskSummary;
}

export function TaskSummaryCard({ summary }: TaskSummaryCardProps) {
  return (
    <div className="mt-3 border border-emerald-200 rounded-xl overflow-hidden">
      <div className="px-4 py-2 bg-emerald-50 border-b border-emerald-200 flex items-center gap-2">
        <FileBarChart size={15} className="text-emerald-600" />
        <h4 className="text-sm font-semibold text-emerald-700">
          任务汇总 · 已确认上架清单（共 {summary.total} 条）
        </h4>
      </div>
      {summary.total === 0 ? (
        <p className="px-4 py-6 text-sm text-gray-400 text-center">
          当前上架清单为空。
        </p>
      ) : (
        <ul className="divide-y divide-gray-100">
          {summary.items.map((item, idx) => (
            <li key={`${item.sku_id || item.product_name}-${idx}`} className="px-4 py-3">
              <div className="flex items-start gap-3">
                <div className="w-7 h-7 bg-emerald-100 rounded-lg flex items-center justify-center shrink-0">
                  <Package size={14} className="text-emerald-700" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-gray-800">{item.product_name}</p>
                  <p className="text-xs text-gray-500 mt-0.5">
                    {[item.sku_id, item.category].filter(Boolean).join(' · ') || '—'}
                  </p>
                  <div className="mt-1.5 flex items-center gap-2 flex-wrap">
                    {item.status && (
                      <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
                        {item.status}
                      </span>
                    )}
                    {item.notes && (
                      <span className="text-xs text-gray-600">{item.notes}</span>
                    )}
                  </div>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
