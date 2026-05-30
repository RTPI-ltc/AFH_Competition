import { Bot, FileText, AlertTriangle, Brain, ArrowRight } from 'lucide-react';
import { useApp } from '../../contexts/AppContext';

const examples = [
  '请基于已选择知识库，回答这个赛事的提交材料有哪些，并列出需要人工确认的事项。',
  '请把课程资料里的核心知识点整理成复习提纲，并生成 5 道练习题。',
  '请检查这份项目申报材料还缺哪些附件、依据来源和风险提示。',
];

export function WelcomePage() {
  const { sendMessage } = useApp();

  return (
    <div className="flex flex-col items-center justify-center min-h-[80vh] px-4">
      {/* Logo */}
      <div className="w-16 h-16 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-2xl flex items-center justify-center mb-6 shadow-lg shadow-indigo-200">
        <Bot size={32} className="text-white" />
      </div>

      {/* Title */}
      <h1 className="text-2xl font-bold text-gray-900 mb-2">知识库 Agent</h1>
      <p className="text-gray-500 text-sm mb-10 text-center max-w-md">
        选择一个 Agent 和多个知识库后提问，系统会按 AgentScope 编排检索证据、
        判断置信度，并保留引用来源供复核。
      </p>

      {/* Features */}
      <div className="grid grid-cols-3 gap-4 max-w-xl mb-10">
        <div className="flex flex-col items-center text-center p-4 bg-indigo-50 rounded-2xl">
          <FileText size={24} className="text-indigo-600 mb-2" />
          <span className="text-xs font-medium text-gray-700">可信问答</span>
          <span className="text-[10px] text-gray-400 mt-1">引用溯源</span>
        </div>
        <div className="flex flex-col items-center text-center p-4 bg-amber-50 rounded-2xl">
          <AlertTriangle size={24} className="text-amber-600 mb-2" />
          <span className="text-xs font-medium text-gray-700">低置信提示</span>
          <span className="text-[10px] text-gray-400 mt-1">人工复核</span>
        </div>
        <div className="flex flex-col items-center text-center p-4 bg-green-50 rounded-2xl">
          <Brain size={24} className="text-green-600 mb-2" />
          <span className="text-xs font-medium text-gray-700">Agent 编排</span>
          <span className="text-[10px] text-gray-400 mt-1">单 Agent 路由</span>
        </div>
      </div>

      {/* Examples */}
      <div className="max-w-xl w-full">
        <p className="text-xs font-medium text-gray-400 mb-3 text-center">快速示例（点击试用）</p>
        <div className="space-y-2">
          {examples.map((example, idx) => (
            <button
              key={idx}
              onClick={() => sendMessage(example)}
              className="flex items-center gap-3 w-full px-4 py-3 text-left text-sm text-gray-600 bg-gray-50 hover:bg-gray-100 rounded-xl border border-gray-200 transition-all group"
            >
              <span className="flex-1 truncate">{example}</span>
              <ArrowRight size={14} className="text-gray-400 group-hover:text-indigo-500 transition-colors shrink-0" />
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
