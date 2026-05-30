import { useState } from 'react';
import { Bot, ChevronDown, Check } from 'lucide-react';
import { useApp } from '../../contexts/AppContext';

export function AgentSection() {
  const { state, dispatch } = useApp();
  const [isOpen, setIsOpen] = useState(true);
  const selectedAgent = state.agentList.find((agent) => agent.id === state.selectedAgentId);

  return (
    <div className="px-2">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 w-full px-3 py-2 text-sm font-medium text-gray-600 hover:bg-gray-200 rounded-lg transition-colors"
      >
        <Bot size={16} />
        <span className="flex-1 text-left">当前 Agent</span>
        <span className="text-[10px] text-gray-400 truncate max-w-24">
          {selectedAgent?.name || '未加载'}
        </span>
        <ChevronDown
          size={14}
          className={`transition-transform ${isOpen ? 'rotate-0' : '-rotate-90'}`}
        />
      </button>

      {isOpen && (
        <div className="mt-1 ml-2 space-y-0.5">
          {state.agentList.map((agent) => {
            const selected = agent.id === state.selectedAgentId;
            return (
              <button
                key={agent.id}
                onClick={() => dispatch({ type: 'SET_SELECTED_AGENT', agentId: agent.id })}
                className={`flex items-start gap-2 w-full px-3 py-2 text-xs rounded-md transition-colors ${
                  selected
                    ? 'bg-blue-50 text-blue-700'
                    : 'text-gray-500 hover:bg-gray-100'
                }`}
              >
                <Bot size={14} className="mt-0.5 shrink-0" />
                <span className="min-w-0 flex-1 text-left">
                  <span className="block font-medium truncate">{agent.name}</span>
                  <span className="block text-[10px] opacity-70 truncate">{agent.scenario}</span>
                </span>
                {selected && <Check size={13} className="mt-0.5 shrink-0" />}
              </button>
            );
          })}

          {state.agentList.length === 0 && (
            <p className="px-3 py-2 text-xs text-gray-400">Agent 列表加载中</p>
          )}
        </div>
      )}
    </div>
  );
}
