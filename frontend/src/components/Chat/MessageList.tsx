import { User, Bot, Loader2 } from 'lucide-react';
import type { Message, RagChunk } from '../../types';
import { RagSourcesCard } from './RagSourcesCard';

interface AgentMessageProps {
  message: Message;
  isStreaming: boolean;
}

function SimpleMarkdown({ text }: { text: string }) {
  const lines = text.split('\n');
  return (
    <div className="space-y-1">
      {lines.map((line, i) => {
        if (!line.trim()) return <br key={i} />;
        const withBold = line.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
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
  const ragChunks = message.metadata?.rag_chunks as RagChunk[] | undefined;
  const knowledgeIds = message.metadata?.knowledge_ids as string[] | undefined;
  const agentName = message.metadata?.agent_name;
  const confidence = message.metadata?.confidence;
  const evidenceNotes = message.metadata?.evidence_notes;
  const followUpQuestions = message.metadata?.follow_up_questions;
  const retrievalMode = message.metadata?.retrieval_mode;
  const gpuMode = message.metadata?.gpu_mode;
  const retrievalLabel = retrievalMode
    ? retrievalMode === 'bm25-only'
      ? '本地 BM25'
      : retrievalMode === 'hybrid'
        ? 'GPU/语义混合'
        : retrievalMode === 'dense'
          ? '语义检索'
          : retrievalMode
    : '';

  return (
    <div className="flex gap-3 px-4 py-4 max-w-3xl mx-auto w-full">
      <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shrink-0 shadow-sm">
        <Bot size={16} className="text-white" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="bg-white border border-gray-200 rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm">
          {message.content ? (
            <>
              {(agentName || confidence) && (
                <div className="mb-2 flex flex-wrap items-center gap-2 text-[11px] text-gray-400">
                  {agentName && <span>Agent：{agentName}</span>}
                  {confidence && <span>置信度：{confidence}</span>}
                  {retrievalLabel && <span>检索：{retrievalLabel}</span>}
                  {gpuMode && <span>GPU：{gpuMode}</span>}
                </div>
              )}
              <SimpleMarkdown text={message.content} />
            </>
          ) : (
            <div className="flex items-center gap-2 text-gray-400 text-sm">
              <Loader2 size={14} className="animate-spin" />
              <span>Agent 思考中...</span>
            </div>
          )}

          {evidenceNotes && evidenceNotes.length > 0 && (
            <div className="mt-3 text-xs text-gray-500 space-y-1">
              {evidenceNotes.map((item, idx) => (
                <p key={idx}>依据边界：{item}</p>
              ))}
            </div>
          )}

          {followUpQuestions && followUpQuestions.length > 0 && (
            <div className="mt-2 text-xs text-gray-500 space-y-1">
              {followUpQuestions.map((item, idx) => (
                <p key={idx}>需补充：{item}</p>
              ))}
            </div>
          )}

          {ragChunks && ragChunks.length > 0 && (
            <RagSourcesCard chunks={ragChunks} knowledgeIds={knowledgeIds} />
          )}

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
