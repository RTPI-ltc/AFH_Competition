import { useEffect, useRef } from 'react';
import { useApp } from '../../contexts/AppContext';
import { AgentMessage, UserMessage } from './MessageList';
import { InputArea } from './InputArea';
import { WelcomePage } from '../common/WelcomePage';
import { AlertCircle, X } from 'lucide-react';

interface ChatAreaProps {
  onOpenKnowledgeModal: () => void;
}

export function ChatArea({ onOpenKnowledgeModal }: ChatAreaProps) {
  const { state, dispatch } = useApp();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [state.messages, state.streamingText]);

  return (
    <div className="flex flex-col h-full bg-white">
      {/* Error banner */}
      {state.error && (
        <div className="flex items-center gap-3 mx-4 mt-3 px-4 py-3 bg-red-50 border border-red-200 rounded-xl">
          <AlertCircle size={16} className="text-red-500 shrink-0" />
          <p className="flex-1 text-sm text-red-700">{state.error}</p>
          <button
            onClick={() => dispatch({ type: 'SET_ERROR', error: null })}
            className="p-1 rounded hover:bg-red-100 text-red-400"
          >
            <X size={14} />
          </button>
        </div>
      )}

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto">
        {state.messages.length === 0 && !state.error ? (
          <WelcomePage />
        ) : (
          <div className="py-4">
            {state.messages.map((msg, idx) => {
              const isLastAgent = idx === state.messages.length - 1 && msg.role === 'agent';
              return msg.role === 'user' ? (
                <UserMessage key={idx} message={msg} />
              ) : (
                <AgentMessage
                  key={idx}
                  message={msg}
                  isStreaming={isLastAgent && state.isLoading}
                />
              );
            })}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input area */}
      <InputArea onOpenKnowledgeModal={onOpenKnowledgeModal} />
    </div>
  );
}
