import { useEffect, useMemo, useState } from 'react';
import { ArrowLeft, BookOpenCheck, ClipboardCheck, GraduationCap, Network, Play, ShieldCheck } from 'lucide-react';
import { useApp } from '../../contexts/AppContext';
import { getAgents } from '../../services/api';
import type { AgentLibraryItem } from '../../types';

interface AgentLibraryPageProps {
  onBack: () => void;
}

type AgentLoadStatus = 'loading' | 'ready' | 'fallback';

const fallbackAgents: AgentLibraryItem[] = [
  {
    id: 'hackathon',
    name: '赛事知识助手',
    scenario: 'AIRS 黑客松 / 创新赛事',
    description: '读取赛事规则、FAQ 和提交要求，帮助参赛者形成可执行的材料清单。',
    capabilities: ['规则问答', '赛题理解', '提交材料核对', '评审标准解释'],
    suggested_knowledge: ['赛事章程', 'FAQ 文档', '评审细则', '提交模板'],
    tools: ['知识库检索', '材料清单生成', '风险项标注'],
    output_modes: ['规则摘要', '提交清单', '评审要点', '人工确认项'],
    risk_controls: ['标注证据来源', '提示缺失材料', '拆分低置信结论'],
  },
  {
    id: 'course',
    name: '课程 AI 助教',
    scenario: '通识课 / 培训课程',
    description: '围绕课程资料回答问题，生成知识点解释、复习路径和练习建议。',
    capabilities: ['课程问答', '概念解释', '知识点对比', '练习题生成'],
    suggested_knowledge: ['课程大纲', '讲义', '阅读材料', '教师答疑记录'],
    tools: ['章节检索', '知识点归纳', '练习清单生成'],
    output_modes: ['知识点解释', '复习提纲', '练习题', '证据不足提示'],
    risk_controls: ['区分资料原文和推断', '提示课程范围外问题', '保留待教师确认项'],
  },
  {
    id: 'application',
    name: '项目申报助手',
    scenario: '大创 / 科研 / 商业计划书',
    description: '把政策、指南和申报材料要求结构化，帮助检查材料完整性。',
    capabilities: ['政策解读', '材料结构化', '附件核对', '申报风险提示'],
    suggested_knowledge: ['申报指南', '政策文件', '模板范文', '往期答疑'],
    tools: ['条件匹配', '材料缺口检查', '下一步行动生成'],
    output_modes: ['申报条件表', '材料缺口清单', '行动计划', '复核问题'],
    risk_controls: ['明确适用条件', '提示截止日期风险', '列出需人工确认的政策边界'],
  },
  {
    id: 'enterprise',
    name: '企业知识库助手',
    scenario: '制度 / 产品 / 培训资料',
    description: '面向内部知识问答和流程核对，帮助沉淀 FAQ 与知识缺口。',
    capabilities: ['制度问答', '流程核对', 'FAQ 沉淀', '知识缺口识别'],
    suggested_knowledge: ['制度手册', '产品文档', '培训资料', '历史问答'],
    tools: ['条款检索', '流程检查', 'FAQ 草稿生成'],
    output_modes: ['引用式回答', '流程步骤', 'FAQ 草稿', '补充资料建议'],
    risk_controls: ['引用具体资料', '提示版本过期风险', '标记跨部门确认项'],
  },
  {
    id: 'trusted',
    name: '可信问答复核 Agent',
    scenario: '证据审查 / 低置信识别',
    description: '复核已有答案的证据链，识别资料冲突、空白和需要人工判断的结论。',
    capabilities: ['证据审查', '冲突识别', '低置信判断', '人工复核清单'],
    suggested_knowledge: ['原始资料', '引用片段', '版本记录', '专家确认记录'],
    tools: ['证据对齐', '冲突检查', '低置信标注'],
    output_modes: ['可确认结论', '低置信结论', '资料冲突', '人工复核清单'],
    risk_controls: ['不把推断写成事实', '分离无证据结论', '要求人工确认高风险答案'],
  },
];

const agentIcons: Record<string, typeof ShieldCheck> = {
  hackathon: ClipboardCheck,
  'hackathon-assistant': ClipboardCheck,
  course: GraduationCap,
  'course-ta': GraduationCap,
  application: BookOpenCheck,
  'project-application': BookOpenCheck,
  enterprise: Network,
  'enterprise-knowledge': Network,
  trusted: ShieldCheck,
  'evidence-review': ShieldCheck,
};

function toTextList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.map((item) => String(item).trim()).filter(Boolean);
}

function normalizeAgents(items: AgentLibraryItem[]): AgentLibraryItem[] {
  return items
    .filter((item) => item?.id && item?.name)
    .map((item) => ({
      id: item.id,
      name: item.name,
      scenario: item.scenario || '知识库问答',
      description: item.description || '基于当前知识库回答问题，并标注证据与风险。',
      capabilities: toTextList(item.capabilities),
      suggested_knowledge: toTextList(item.suggested_knowledge),
      tools: toTextList(item.tools),
      output_modes: toTextList(item.output_modes),
      risk_controls: toTextList(item.risk_controls),
    }));
}

function renderTags(items: string[], emptyText: string) {
  if (items.length === 0) {
    return <span className="text-xs text-gray-400">{emptyText}</span>;
  }
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map((item) => (
        <span key={item} className="rounded-md bg-gray-100 px-2 py-1 text-xs text-gray-700">
          {item}
        </span>
      ))}
    </div>
  );
}

export function AgentLibraryPage({ onBack }: AgentLibraryPageProps) {
  const { state, dispatch, loadAgents } = useApp();
  const [agents, setAgents] = useState<AgentLibraryItem[]>(fallbackAgents);
  const [loadStatus, setLoadStatus] = useState<AgentLoadStatus>('loading');
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function loadAgentCards() {
      setLoadStatus('loading');
      setLoadError(null);
      try {
        const remoteAgents = normalizeAgents(await getAgents());
        if (!active) return;
        if (remoteAgents.length === 0) {
          setAgents(fallbackAgents);
          setLoadStatus('fallback');
          setLoadError('后端暂未返回 Agent 配置。');
          return;
        }
        setAgents(remoteAgents);
        dispatch({ type: 'SET_AGENTS', agents: remoteAgents });
        setLoadStatus('ready');
      } catch (err) {
        if (!active) return;
        setAgents(fallbackAgents);
        setLoadStatus('fallback');
        setLoadError(err instanceof Error ? err.message : 'Agent 列表加载失败。');
      }
    }

    void loadAgentCards();
    return () => {
      active = false;
    };
  }, [dispatch, loadAgents]);

  const statusMessage = useMemo(() => {
    if (loadStatus === 'loading') {
      return '正在加载 /api/agents，当前先展示本地知识库 Agent 场景。';
    }
    if (loadStatus === 'fallback') {
      return `后端 Agent 暂不可用，已切换到本地 5 个场景。${loadError ? `原因：${loadError}` : ''}`;
    }
    return '已从后端同步 Agent 配置。';
  }, [loadError, loadStatus]);

  const statusClassName = loadStatus === 'ready'
    ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
    : loadStatus === 'loading'
      ? 'border-blue-200 bg-blue-50 text-blue-700'
      : 'border-amber-200 bg-amber-50 text-amber-800';

  return (
    <div className="flex h-full flex-col bg-white">
      <div className="border-b border-gray-200 px-6 py-4">
        <div className="mx-auto flex max-w-5xl items-center gap-3">
          <button onClick={onBack} className="rounded-lg p-2 text-gray-500 transition-colors hover:bg-gray-100">
            <ArrowLeft size={18} />
          </button>
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-100">
            <ShieldCheck size={16} className="text-indigo-600" />
          </div>
          <div className="min-w-0 flex-1">
            <h1 className="text-lg font-semibold text-gray-900">Agent 库</h1>
            <p className="mt-0.5 text-xs text-gray-500">选择一个知识库 Agent，基于当前选中的资料启动任务。</p>
          </div>
          <span className="rounded-full bg-gray-100 px-3 py-1 text-xs text-gray-500">
            已选 {state.selectedKnowledge.length} 个知识库
          </span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        <div className={`mx-auto mb-4 max-w-5xl rounded-lg border px-4 py-3 text-sm ${statusClassName}`}>
          {statusMessage}
        </div>

        <div className="mx-auto grid max-w-5xl grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {agents.map((agent) => {
            const Icon = agentIcons[agent.id] ?? ShieldCheck;
            return (
              <div key={agent.id} className="flex min-h-[25rem] flex-col rounded-lg border border-gray-200 bg-white p-4 transition-all hover:border-indigo-200 hover:shadow-sm">
                <div className="flex items-start gap-3">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-indigo-50">
                    <Icon size={20} className="text-indigo-600" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <h2 className="text-sm font-semibold text-gray-900">{agent.name}</h2>
                    <p className="mt-0.5 text-xs text-indigo-600">{agent.scenario}</p>
                  </div>
                </div>

                <p className="mt-3 min-h-[3.25rem] text-sm leading-relaxed text-gray-600">
                  {agent.description}
                </p>

                <div className="mt-3 space-y-3">
                  <div>
                    <p className="mb-1.5 text-xs font-medium text-gray-500">能力</p>
                    {renderTags(agent.capabilities, '待配置能力')}
                  </div>
                  <div>
                    <p className="mb-1.5 text-xs font-medium text-gray-500">输出</p>
                    {renderTags(agent.output_modes, '待配置输出')}
                  </div>
                  <div>
                    <p className="mb-1.5 text-xs font-medium text-gray-500">风险控制</p>
                    {renderTags(agent.risk_controls, '待配置风险控制')}
                  </div>
                </div>

                <button
                  type="button"
                  onClick={() => {
                    dispatch({ type: 'SET_SELECTED_AGENT', agentId: agent.id });
                    onBack();
                  }}
                  disabled={state.isLoading || state.selectedAgentId === agent.id}
                  className="mt-auto inline-flex items-center justify-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-indigo-700 disabled:opacity-50"
                >
                  <Play size={14} />
                  {state.selectedAgentId === agent.id ? '当前 Agent' : '选择 Agent'}
                </button>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
