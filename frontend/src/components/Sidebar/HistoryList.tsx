import { useState } from 'react';
import { useApp } from '../../contexts/AppContext';
import { MessageSquare, Trash2, FileBarChart, Check, X } from 'lucide-react';
import { formatRelativeTime } from '../../utils/time';

interface HistoryListProps {
  onSummarize: (taskId: string) => void;
}

export function HistoryList({ onSummarize }: HistoryListProps) {
  const { state, selectTask, deleteTaskHistory, renameTask } = useApp();
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState('');

  const startRename = (id: string, title: string) => {
    setEditingId(id);
    setEditName(title.replace('…', ''));
  };

  const confirmRename = () => {
    if (editingId && editName.trim()) {
      renameTask(editingId, editName.trim());
    }
    setEditingId(null);
    setEditName('');
  };

  if (state.history.length === 0) {
    return (
      <div className="px-3 py-4 text-xs text-gray-400 text-center">
        暂无历史记录
      </div>
    );
  }

  return (
    <div className="px-2 space-y-0.5">
      {state.history.map((item) => {
        const isEditing = editingId === item.task_id;
        return (
          <div
            key={item.task_id}
            className={`group flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer transition-colors text-sm ${
              state.currentTaskId === item.task_id
                ? 'bg-indigo-50 text-indigo-700'
                : 'text-gray-600 hover:bg-gray-100'
            }`}
            onClick={() => !isEditing && selectTask(item.task_id)}
          >
            <MessageSquare size={14} className="shrink-0" />

            {isEditing ? (
              <div className="flex-1 flex items-center gap-1 min-w-0" onClick={(e) => e.stopPropagation()}>
                <input
                  type="text"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') confirmRename(); if (e.key === 'Escape') setEditingId(null); }}
                  className="flex-1 px-1 py-0 text-xs border border-indigo-300 rounded bg-white focus:outline-none focus:ring-1 focus:ring-indigo-500"
                  autoFocus
                />
                <button onClick={confirmRename} className="p-0.5 rounded hover:bg-green-100 text-gray-400 hover:text-green-600">
                  <Check size={12} />
                </button>
                <button onClick={() => setEditingId(null)} className="p-0.5 rounded hover:bg-red-100 text-gray-400 hover:text-red-500">
                  <X size={12} />
                </button>
              </div>
            ) : (
              <div
                className="flex-1 min-w-0"
                onDoubleClick={(e) => { e.stopPropagation(); startRename(item.task_id, item.title); }}
                title="双击重命名"
              >
                <p className="truncate text-xs">{item.title}</p>
                <p className="text-[10px] text-gray-400">{formatRelativeTime(item.created_at)}</p>
              </div>
            )}

            {!isEditing && (
              <>
                <button onClick={(e) => { e.stopPropagation(); onSummarize(item.task_id); }}
                  className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-emerald-100 text-gray-400 hover:text-emerald-600 transition-all" title="汇总">
                  <FileBarChart size={12} />
                </button>
                <button onClick={(e) => { e.stopPropagation(); deleteTaskHistory(item.task_id); }}
                  className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-red-100 text-gray-400 hover:text-red-500 transition-all" title="删除">
                  <Trash2 size={12} />
                </button>
              </>
            )}
          </div>
        );
      })}
    </div>
  );
}
