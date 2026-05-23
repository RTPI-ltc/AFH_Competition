import { useApp } from '../../contexts/AppContext';
import { Library, ChevronDown, Upload, BookOpen } from 'lucide-react';
import { useState } from 'react';

export function KnowledgeSection() {
  const { state, dispatch } = useApp();
  const [isOpen, setIsOpen] = useState(true);

  return (
    <div className="px-2">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 w-full px-3 py-2 text-sm font-medium text-gray-600 hover:bg-gray-200 rounded-lg transition-colors"
      >
        <Library size={16} />
        <span className="flex-1 text-left">知识库</span>
        <ChevronDown
          size={14}
          className={`transition-transform ${isOpen ? 'rotate-0' : '-rotate-90'}`}
        />
      </button>

      {isOpen && (
        <div className="mt-1 ml-2 space-y-0.5">
          {state.knowledgeList.map((kb) => (
            <button
              key={kb.id}
              onClick={() => dispatch({ type: 'TOGGLE_KNOWLEDGE_SELECTION', id: kb.id })}
              className={`flex items-center gap-2 w-full px-3 py-1.5 text-xs rounded-md transition-colors ${
                state.selectedKnowledge.includes(kb.id)
                  ? 'bg-indigo-50 text-indigo-700'
                  : 'text-gray-500 hover:bg-gray-100'
              }`}
            >
              {kb.type === 'official' ? (
                <BookOpen size={14} />
              ) : (
                <Upload size={14} />
              )}
              <span className="truncate flex-1 text-left">{kb.name}</span>
              {state.selectedKnowledge.includes(kb.id) && (
                <span className="w-2 h-2 rounded-full bg-indigo-500" />
              )}
            </button>
          ))}

          {state.knowledgeList.length === 0 && (
            <p className="px-3 py-2 text-xs text-gray-400">暂无知识库，请先导入</p>
          )}
        </div>
      )}
    </div>
  );
}
