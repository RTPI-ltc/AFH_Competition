import { User, Bot, Loader2 } from 'lucide-react';
import type { Message } from '../../types';
import { CheckListCard } from './CheckListCard';
import { RiskAlert } from './RiskAlert';

interface AgentMessageProps {
  message: Message;
  isStreaming: boolean;
}

function SimpleMarkdown({ text }: { text: string }) {
  // Simple markdown rendering: handle bold, lists, paragraphs
  const lines = text.split('\n');
  return (
    <div className="space-y-1">
      {lines.map((line, i) => {
        if (!line.trim()) return <br key={i} />;
        // Bold
        const withBold = line.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        // Inline code
        const withCode = withBold.replace(/`(.*?)`/g, '<code class="bg-gray-100 px-1 py-0.5 rounded text-xs text-pink-600">$1</code>');
        return (
          <p
            key={i}
            className="text-sm leading-relaxed text-gray-700"
            dangerouslySetInnerHTML={{ __html: withCode }}
          />
        );
      })}
    </div>
  );
}

export function AgentMessage({ message, isStreaming }: AgentMessageProps) {
  const checklist = message.metadata?.checklist as Array<{
    condition: string;
    priority: 'high' | 'medium' | 'low';
    detail?: string;
    checked?: boolean;
  }> | undefined;
  const risks = message.metadata?.risks as Array<{
    description: string;
    severity: 'high' | 'medium';
  }> | undefined;
  const needsClarification = message.metadata?.needs_clarification as string[] | undefined;

  return (
    <div className="flex gap-3 px-4 py-4 max-w-3xl mx-auto w-full">
      <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shrink-0 shadow-sm">
        <Bot size={16} className="text-white" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="bg-white border border-gray-200 rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm">
          {message.content ? (
            <SimpleMarkdown text={message.content} />
          ) : (
            <div className="flex items-center gap-2 text-gray-400 text-sm">
              <Loader2 size={14} className="animate-spin" />
              <span>Agent思考中...</span>
            </div>
          )}

          {/* Checklist */}
          {checklist && checklist.length > 0 && (
            <CheckListCard items={checklist} onCheckChange={(updated) => {
              if (message.metadata) {
                message.metadata.checklist = updated;
              }
            }} />
          )}

          {/* Risks */}
          {risks && risks.length > 0 && (
            <RiskAlert risks={risks} />
          )}

          {/* Clarification needed */}
          {needsClarification && needsClarification.length > 0 && (
            <div className="mt-3 border border-amber-200 bg-amber-50 rounded-xl p-4">
              <h4 className="text-sm font-semibold text-amber-800 mb-2 flex items-center gap-1.5">
                <span className="text-lg">❓</span> 需要确认/补充的信息
              </h4>
              <ul className="space-y-1">
                {needsClarification.map((item, idx) => (
                  <li key={idx} className="text-sm text-amber-700 flex items-start gap-2">
                    <span className="text-amber-400 mt-0.5">•</span>
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Streaming indicator */}
          {isStreaming && message.content && (
            <span className="inline-block w-2 h-4 bg-indigo-500 animate-pulse ml-0.5 rounded-sm" />
          )}
        </div>
      </div>
    </div>
  );
}

export function UserMessage({ message }: { message: Message }) {
  return (
    <div className="flex gap-3 px-4 py-4 max-w-3xl mx-auto w-full justify-end">
      <div className="flex-1 min-w-0 flex justify-end">
        <div className="bg-indigo-600 text-white rounded-2xl rounded-tr-sm px-4 py-3 shadow-sm max-w-[80%]">
          <p className="text-sm leading-relaxed whitespace-pre-wrap">{message.content}</p>
        </div>
      </div>
      <div className="w-8 h-8 rounded-xl bg-gray-200 flex items-center justify-center shrink-0">
        <User size={16} className="text-gray-600" />
      </div>
    </div>
  );
}
