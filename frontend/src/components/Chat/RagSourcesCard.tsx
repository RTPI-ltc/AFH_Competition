import { useState } from 'react';
import { BookOpen, ChevronDown, FileText, Brain, Hash, Target } from 'lucide-react';
import type { RagChunk } from '../../types';
import { useApp } from '../../contexts/AppContext';

interface RagSourcesCardProps {
  chunks: RagChunk[];
  knowledgeIds?: string[];
}

type HitKind = 'both' | 'dense' | 'bm25' | 'unknown';

function hitKind(chunk: RagChunk): HitKind {
  const dense = chunk.dense_score != null;
  const bm25 = chunk.bm25_score != null;
  if (dense && bm25) return 'both';
  if (dense) return 'dense';
  if (bm25) return 'bm25';
  return 'unknown';
}

const HIT_META: Record<HitKind, { label: string; pill: string; Icon: typeof Brain }> = {
  both: { label: '双通道命中', pill: 'bg-emerald-100 text-emerald-700', Icon: Target },
  dense: { label: '语义命中', pill: 'bg-indigo-100 text-indigo-700', Icon: Brain },
  bm25: { label: '关键词命中', pill: 'bg-amber-100 text-amber-700', Icon: Hash },
  unknown: { label: '已检索', pill: 'bg-gray-100 text-gray-600', Icon: BookOpen },
};

function formatNum(value: number | null | undefined, digits = 2): string {
  if (value == null || Number.isNaN(value)) return '—';
  return value.toFixed(digits);
}

function densePct(value: number | null | undefined): number {
  if (value == null || Number.isNaN(value)) return 0;
  // cosine similarity in [0, 1] for normalized embeddings
  return Math.min(100, Math.max(0, value * 100));
}

function bm25Pct(value: number | null | undefined, maxBm25: number): number {
  if (value == null || Number.isNaN(value) || maxBm25 <= 0) return 0;
  return Math.min(100, Math.max(0, (value / maxBm25) * 100));
}

export function RagSourcesCard({ chunks, knowledgeIds }: RagSourcesCardProps) {
  const [expanded, setExpanded] = useState(false);
  const { state } = useApp();

  if (!chunks || chunks.length === 0) return null;

  const kbNameById = new Map<string, string>();
  state.knowledgeList.forEach((kb) => kbNameById.set(kb.id, kb.name));

  const sorted = [...chunks].sort(
    (a, b) => (b.rrf_score ?? b.score ?? 0) - (a.rrf_score ?? a.score ?? 0),
  );

  const maxBm25 = sorted.reduce(
    (acc, c) => Math.max(acc, c.bm25_score ?? 0),
    0,
  );
  const hybridCount = sorted.filter((c) => hitKind(c) === 'both').length;
  const denseOnly = sorted.filter((c) => hitKind(c) === 'dense').length;
  const bm25Only = sorted.filter((c) => hitKind(c) === 'bm25').length;

  const kbCounts = new Map<string, number>();
  chunks.forEach((c) => kbCounts.set(c.kb_id, (kbCounts.get(c.kb_id) ?? 0) + 1));
  const queriedButUnused = (knowledgeIds ?? []).filter((id) => !kbCounts.has(id));

  return (
    <div className="mt-3 border border-indigo-100 rounded-xl overflow-hidden bg-gradient-to-b from-indigo-50/40 to-white">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center gap-2 px-4 py-2.5 bg-indigo-50/70 hover:bg-indigo-100/70 transition-colors text-left"
      >
        <div className="w-7 h-7 rounded-lg bg-indigo-100 flex items-center justify-center shrink-0">
          <BookOpen size={14} className="text-indigo-600" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-semibold text-indigo-900">混合检索命中</span>
            <span className="text-xs px-1.5 py-0.5 rounded-full bg-indigo-200 text-indigo-700 font-medium">
              {chunks.length}
            </span>
            <span className="text-[11px] text-indigo-700/70">
              · {kbCounts.size} 个知识库
            </span>
            <div className="ml-auto flex items-center gap-1.5">
              {hybridCount > 0 && (
                <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-emerald-100 text-emerald-700 font-medium flex items-center gap-1">
                  <Target size={10} /> {hybridCount}
                </span>
              )}
              {denseOnly > 0 && (
                <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-indigo-100 text-indigo-700 font-medium flex items-center gap-1">
                  <Brain size={10} /> {denseOnly}
                </span>
              )}
              {bm25Only > 0 && (
                <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-700 font-medium flex items-center gap-1">
                  <Hash size={10} /> {bm25Only}
                </span>
              )}
            </div>
          </div>
        </div>
        <ChevronDown
          size={16}
          className={`text-indigo-500 shrink-0 transition-transform ${expanded ? 'rotate-180' : ''}`}
        />
      </button>

      {expanded && (
        <div className="px-3 py-3 space-y-2">
          {sorted.map((chunk, idx) => {
            const kind = hitKind(chunk);
            const meta = HIT_META[kind];
            const KindIcon = meta.Icon;
            const kbName = kbNameById.get(chunk.kb_id) || chunk.kb_id;
            return (
              <div
                key={`${chunk.kb_id}-${idx}`}
                className="border border-gray-200 rounded-lg bg-white px-3 py-2.5 hover:border-indigo-200 transition-colors"
              >
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-[10px] font-bold w-5 h-5 rounded-full flex items-center justify-center bg-gray-100 text-gray-600">
                    {idx + 1}
                  </span>
                  <FileText size={12} className="text-gray-400 shrink-0" />
                  <span className="text-xs font-medium text-gray-800 truncate" title={`${kbName} · ${chunk.source_file}`}>
                    {kbName}
                  </span>
                  <span className="text-[11px] text-gray-400 truncate flex-1" title={chunk.source_file}>
                    · {chunk.source_file || '未命名来源'}
                  </span>
                  <span
                    className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium flex items-center gap-1 shrink-0 ${meta.pill}`}
                    title={meta.label}
                  >
                    <KindIcon size={10} />
                    {meta.label}
                  </span>
                </div>

                <div className="grid grid-cols-[auto_1fr_auto] gap-x-2 gap-y-1 items-center mb-2 text-[11px]">
                  <span className="flex items-center gap-1 text-indigo-600">
                    <Brain size={11} /> 语义
                  </span>
                  <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full bg-indigo-400 transition-all duration-300"
                      style={{ width: `${densePct(chunk.dense_score)}%` }}
                    />
                  </div>
                  <span className="tabular-nums text-gray-500">{formatNum(chunk.dense_score)}</span>

                  <span className="flex items-center gap-1 text-amber-600">
                    <Hash size={11} /> 关键词
                  </span>
                  <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full bg-amber-400 transition-all duration-300"
                      style={{ width: `${bm25Pct(chunk.bm25_score, maxBm25)}%` }}
                    />
                  </div>
                  <span className="tabular-nums text-gray-500">{formatNum(chunk.bm25_score)}</span>

                  <span className="flex items-center gap-1 text-emerald-700 font-medium">
                    <Target size={11} /> 融合
                  </span>
                  <div className="h-1.5 bg-emerald-100 rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full bg-emerald-500 transition-all duration-300"
                      style={{ width: `${Math.min(100, (chunk.rrf_score ?? chunk.score ?? 0) * 100 * 30)}%` }}
                    />
                  </div>
                  <span className="tabular-nums text-emerald-700 font-medium">
                    {formatNum(chunk.rrf_score ?? chunk.score, 3)}
                  </span>
                </div>

                <p className="text-xs text-gray-600 leading-relaxed border-l-2 border-indigo-100 pl-2">
                  {chunk.snippet || '(无摘要)'}
                </p>
              </div>
            );
          })}
          {queriedButUnused.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5 mt-2 px-1 text-[11px] text-gray-500">
              <span>已检索但未命中：</span>
              {queriedButUnused.map((id) => (
                <span key={id} className="px-1.5 py-0.5 rounded bg-gray-100 text-gray-500">
                  {kbNameById.get(id) || id}
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
