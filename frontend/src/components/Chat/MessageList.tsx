import { User, Bot, Loader2, CheckCircle2, SlidersHorizontal, Sparkles } from 'lucide-react';
import type { ConfirmationRequest, Message, RagChunk, RecommendationItem } from '../../types';
import { CheckListCard } from './CheckListCard';
import { RiskAlert } from './RiskAlert';
import { RagSourcesCard } from './RagSourcesCard';
import { useApp } from '../../contexts/AppContext';

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
  const { sendMessage, state } = useApp();
  const checklist = message.metadata?.checklist;
  const risks = message.metadata?.risks;
  const needsClarification = message.metadata?.needs_clarification;
  const recommendations = message.metadata?.recommendations as RecommendationItem[] | undefined;
  const priorityAnalysis = message.metadata?.priority_analysis;
  const confirmation = message.metadata?.confirmation as ConfirmationRequest | undefined;
  const ragChunks = message.metadata?.rag_chunks as RagChunk[] | undefined;
  const knowledgeIds = message.metadata?.knowledge_ids as string[] | undefined;

  const priorityLabel = {
    high: '高优先级',
    medium: '中优先级',
    low: '低优先级',
  };

  const priorityClass = {
    high: 'bg-red-50 text-red-700 border-red-200',
    medium: 'bg-amber-50 text-amber-700 border-amber-200',
    low: 'bg-gray-50 text-gray-600 border-gray-200',
  };

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
              <span>Agent 思考中...</span>
            </div>
          )}

          {recommendations && recommendations.length > 0 && (
            <div className="mt-3 border border-indigo-100 rounded-xl overflow-hidden">
              <div className="px-4 py-2 bg-indigo-50 border-b border-indigo-100 flex items-center gap-2">
                <Sparkles size={15} className="text-indigo-600" />
                <h4 className="text-sm font-semibold text-indigo-700">推荐上架商品</h4>
              </div>
              <div className="divide-y divide-gray-100">
                {recommendations.map((item) => (
                  <div key={item.sku_id || item.product_name} className="px-4 py-3">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-gray-800">{item.product_name}</p>
                        <p className="text-xs text-gray-500 mt-0.5">{item.sku_id} · 评分 {item.score}</p>
                      </div>
                      <span className={`shrink-0 text-[10px] px-2 py-0.5 rounded-full border font-medium ${priorityClass[item.priority]}`}>
                        {priorityLabel[item.priority]}
                      </span>
                    </div>
                    <p className="text-xs text-gray-600 mt-2 leading-relaxed">{item.reason}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {priorityAnalysis && priorityAnalysis.length > 0 && (
            <div className="mt-3 border border-gray-200 rounded-xl p-4 bg-gray-50/60">
              <h4 className="text-sm font-semibold text-gray-800 mb-2 flex items-center gap-1.5">
                <SlidersHorizontal size={15} className="text-gray-500" />
                优先级分析
              </h4>
              <ul className="space-y-1.5">
                {priorityAnalysis.map((item, idx) => (
                  <li key={idx} className="text-sm text-gray-600 leading-relaxed flex gap-2">
                    <span className="text-gray-400 shrink-0">{idx + 1}.</span>
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {checklist && checklist.length > 0 && (
            <CheckListCard items={checklist} onCheckChange={() => {}} />
          )}

          {risks && risks.length > 0 && (
            <RiskAlert risks={risks} />
          )}

          {needsClarification && needsClarification.length > 0 && (
            <div className="mt-3 border border-amber-200 bg-amber-50 rounded-xl p-4">
              <h4 className="text-sm font-semibold text-amber-800 mb-2 flex items-center gap-1.5">
                <SlidersHorizontal size={15} className="text-amber-500" />
                需要人工确认的信息
              </h4>
              <ul className="space-y-1">
                {needsClarification.map((item, idx) => (
                  <li key={idx} className="text-sm text-amber-700 flex items-start gap-2">
                    <span className="text-amber-400 mt-0.5">-</span>
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {confirmation?.required && (
            <div className="mt-3 border border-indigo-200 bg-indigo-50 rounded-xl p-4">
              <h4 className="text-sm font-semibold text-indigo-800 mb-2 flex items-center gap-1.5">
                <CheckCircle2 size={15} className="text-indigo-600" />
                等待确认
              </h4>
              <p className="text-sm text-indigo-700 mb-3">
                {confirmation.question || '是否确认按这个方案推进？'}
              </p>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  disabled={state.isLoading}
                  onClick={() => sendMessage('确认执行上一个上架方案')}
                  className="px-3 py-1.5 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors"
                >
                  {confirmation.confirm_label || '确认方案'}
                </button>
                <button
                  type="button"
                  disabled={state.isLoading}
                  onClick={() => sendMessage('我想继续调整上一个上架方案')}
                  className="px-3 py-1.5 rounded-lg bg-white text-indigo-700 border border-indigo-200 text-sm font-medium hover:bg-indigo-100 disabled:opacity-50 transition-colors"
                >
                  {confirmation.revise_label || '继续调整'}
                </button>
              </div>
            </div>
          )}

          {confirmation?.status === 'confirmed' && (
            <div className="mt-3 flex items-center gap-2 text-sm text-green-700 bg-green-50 border border-green-200 rounded-xl px-4 py-3">
              <CheckCircle2 size={15} className="text-green-600" />
              方案已确认，推荐商品已写入上架清单。
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
