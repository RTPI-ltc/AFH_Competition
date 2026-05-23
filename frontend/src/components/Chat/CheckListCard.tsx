import { useState, useEffect } from 'react';
import type { CheckListItem } from '../../types';

interface CheckListCardProps {
  items: CheckListItem[];
  onCheckChange?: (checkedItems: CheckListItem[]) => void;
}

const priorityColors = {
  high: 'border-l-red-500 bg-red-50/50',
  medium: 'border-l-amber-500 bg-amber-50/50',
  low: 'border-l-gray-300 bg-gray-50/50',
};

const priorityColorsChecked = {
  high: 'border-l-green-500 bg-green-50/70',
  medium: 'border-l-green-400 bg-green-50/50',
  low: 'border-l-gray-200 bg-gray-100/50',
};

const priorityBadges = {
  high: '高优先级',
  medium: '中优先级',
  low: '建议',
};

export function CheckListCard({ items, onCheckChange }: CheckListCardProps) {
  const [checkedSet, setCheckedSet] = useState<Set<number>>(new Set());

  // Sync with props if items change (new message)
  useEffect(() => {
    const initial = new Set<number>();
    items.forEach((item, idx) => {
      if (item.checked) initial.add(idx);
    });
    setCheckedSet(initial);
  }, [items]);

  const toggle = (idx: number) => {
    setCheckedSet((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) {
        next.delete(idx);
      } else {
        next.add(idx);
      }
      // Notify parent
      if (onCheckChange) {
        const updated = items.map((item, i) => ({
          ...item,
          checked: next.has(i),
        }));
        onCheckChange(updated);
      }
      return next;
    });
  };

  const checkedCount = checkedSet.size;
  const total = items.length;
  const progress = total > 0 ? Math.round((checkedCount / total) * 100) : 0;

  return (
    <div className="mt-3 border border-gray-200 rounded-xl overflow-hidden">
      {/* Header with progress */}
      <div className="bg-indigo-50 px-4 py-2 border-b border-indigo-100">
        <div className="flex items-center justify-between mb-1.5">
          <h4 className="text-sm font-semibold text-indigo-700 flex items-center gap-1.5">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="3" y="3" width="18" height="18" rx="3" />
              <path d="M9 12l2 2 4-4" />
            </svg>
            执行检查清单
          </h4>
          <span className={`text-xs font-medium ${
            progress === 100 ? 'text-green-600' : progress > 0 ? 'text-indigo-600' : 'text-gray-400'
          }`}>
            {checkedCount}/{total}
          </span>
        </div>
        {/* Progress bar */}
        <div className="w-full h-1.5 bg-indigo-100 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-300 ${
              progress === 100 ? 'bg-green-500' : 'bg-indigo-500'
            }`}
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* Items */}
      <div className="divide-y divide-gray-100">
        {items.map((item, idx) => {
          const isChecked = checkedSet.has(idx);
          return (
            <div
              key={idx}
              className={`px-4 py-3 border-l-4 transition-colors duration-200 ${
                isChecked
                  ? priorityColorsChecked[item.priority] || 'border-l-green-400 bg-green-50/50'
                  : priorityColors[item.priority] || ''
              }`}
            >
              <div className="flex items-start gap-3">
                <input
                  type="checkbox"
                  checked={isChecked}
                  onChange={() => toggle(idx)}
                  className="mt-0.5 w-4 h-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500 cursor-pointer"
                />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span
                      className={`text-sm transition-all ${
                        isChecked ? 'text-gray-400 line-through' : 'text-gray-800'
                      }`}
                    >
                      {item.condition}
                    </span>
                    <span
                      className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${
                        isChecked
                          ? 'bg-green-100 text-green-700'
                          : item.priority === 'high'
                            ? 'bg-red-100 text-red-700'
                            : item.priority === 'medium'
                              ? 'bg-amber-100 text-amber-700'
                              : 'bg-gray-100 text-gray-600'
                      }`}
                    >
                      {isChecked ? '✓ 已确认' : priorityBadges[item.priority]}
                    </span>
                  </div>
                  {item.detail && (
                    <p className={`text-xs mt-0.5 ${isChecked ? 'text-gray-300' : 'text-gray-500'}`}>
                      {item.detail}
                    </p>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
