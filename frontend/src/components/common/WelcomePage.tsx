import { Bot, FileText, AlertTriangle, HelpCircle, ArrowRight } from 'lucide-react';
import { useApp } from '../../contexts/AppContext';

const examples = [
  '天猫618大促选品规则：参与商品近30天销量≥100件，好评率≥95%，库存≥500件',
  '京东双11活动：DSR≥4.8分，开店≥90天，近30天销量≥50件',
  '拼多多百亿补贴：品牌正品授权，全网最低价85折，单SKU库存≥1000件',
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
      <h1 className="text-2xl font-bold text-gray-900 mb-2">Aurelius Agent</h1>
      <p className="text-gray-500 text-sm mb-10 text-center max-w-md">
        输入活动规则文本，Agent将自动解析规则条件，生成结构化执行检查清单，
        识别潜在风险点，并标注需要人工确认的信息。
      </p>

      {/* Features */}
      <div className="grid grid-cols-3 gap-4 max-w-xl mb-10">
        <div className="flex flex-col items-center text-center p-4 bg-indigo-50 rounded-2xl">
          <FileText size={24} className="text-indigo-600 mb-2" />
          <span className="text-xs font-medium text-gray-700">规则解析</span>
          <span className="text-[10px] text-gray-400 mt-1">自动提取条件</span>
        </div>
        <div className="flex flex-col items-center text-center p-4 bg-amber-50 rounded-2xl">
          <AlertTriangle size={24} className="text-amber-600 mb-2" />
          <span className="text-xs font-medium text-gray-700">风险提示</span>
          <span className="text-[10px] text-gray-400 mt-1">识别潜在风险</span>
        </div>
        <div className="flex flex-col items-center text-center p-4 bg-green-50 rounded-2xl">
          <HelpCircle size={24} className="text-green-600 mb-2" />
          <span className="text-xs font-medium text-gray-700">需确认项</span>
          <span className="text-[10px] text-gray-400 mt-1">标注待补充</span>
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
