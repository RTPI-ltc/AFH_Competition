import { Send, Loader2, Plus, Library, X } from 'lucide-react';
import { useState, useRef, type KeyboardEvent } from 'react';
import { useApp } from '../../contexts/AppContext';

interface InputAreaProps {
  onOpenKnowledgeModal: () => void;
}

export function InputArea({ onOpenKnowledgeModal }: InputAreaProps) {
  const [input, setInput] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const { sendMessage, state, dispatch } = useApp();

  const handleSend = () => {
    const trimmed = input.trim();
    if (!trimmed || state.isLoading) return;
    dispatch({ type: 'SET_ERROR', error: null });
    sendMessage(trimmed);
    setInput('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    const el = e.target;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 200) + 'px';
  };

  const selectedKbs = state.knowledgeList.filter((kb) =>
    state.selectedKnowledge.includes(kb.id),
  );

  const unselectedKbs = state.knowledgeList.filter(
    (kb) => !state.selectedKnowledge.includes(kb.id),
  );

  return (
    <div className="border-t border-gray-200 bg-white p-4">
      <div className="max-w-3xl mx-auto">
        {/* Knowledge base selector chips */}
        <div className="flex flex-wrap items-center gap-1.5 mb-3">
          <span className="text-[11px] text-gray-400 shrink-0 mr-0.5 flex items-center gap-1">
            <Library size={12} />
            引用知识库:
          </span>

          {/* Selected chips */}
          {selectedKbs.map((kb) => (
            <button
              key={kb.id}
              onClick={() => dispatch({ type: 'TOGGLE_KNOWLEDGE_SELECTION', id: kb.id })}
              className="flex items-center gap-1 px-2 py-1 rounded-lg text-[11px] font-medium bg-indigo-100 text-indigo-700 border border-indigo-200 hover:bg-indigo-200 transition-colors"
            >
              {kb.name.length > 12 ? kb.name.slice(0, 12) + '…' : kb.name}
              <X size={10} />
            </button>
          ))}

          {/* Unselected chips */}
          {unselectedKbs.map((kb) => (
            <button
              key={kb.id}
              onClick={() => dispatch({ type: 'TOGGLE_KNOWLEDGE_SELECTION', id: kb.id })}
              className="px-2 py-1 rounded-lg text-[11px] text-gray-500 bg-gray-100 border border-gray-200 hover:bg-gray-200 hover:text-gray-700 transition-colors"
            >
              {kb.name.length > 12 ? kb.name.slice(0, 12) + '…' : kb.name}
            </button>
          ))}

          {/* Add knowledge button */}
          <button
            onClick={onOpenKnowledgeModal}
            className="flex items-center gap-0.5 px-2 py-1 rounded-lg text-[11px] text-gray-400 border border-dashed border-gray-300 hover:border-indigo-300 hover:text-indigo-500 transition-colors"
            title="导入新知识库"
          >
            <Plus size={12} />
            导入
          </button>
        </div>

        {/* Input row */}
        <div className="flex items-end gap-3">
          <div className="flex-1 relative">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={handleInput}
              onKeyDown={handleKeyDown}
              placeholder={
                state.selectedKnowledge.length > 0
                  ? `已选择 ${state.selectedKnowledge.length} 个知识库，输入规则文本...`
                  : '输入活动规则文本，Agent将为您解析...'
              }
              rows={1}
              className="w-full resize-none rounded-xl border border-gray-300 bg-gray-50 px-4 py-3 pr-12 text-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all"
              disabled={state.isLoading}
            />
          </div>
          <button
            onClick={handleSend}
            disabled={!input.trim() || state.isLoading}
            className="shrink-0 p-3 rounded-xl bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-sm"
          >
            {state.isLoading ? (
              <Loader2 size={18} className="animate-spin" />
            ) : (
              <Send size={18} />
            )}
          </button>
        </div>

        {/* Hint */}
        <p className="text-center text-[11px] text-gray-400 mt-2">
          Enter 发送 · Shift+Enter 换行
          {selectedKbs.length > 0 && (
            <span className="text-indigo-500"> · 已选 {selectedKbs.length} 个知识库</span>
          )}
        </p>
      </div>
    </div>
  );
}
