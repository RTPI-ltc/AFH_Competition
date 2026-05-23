import { useState } from 'react';
import { useApp } from '../../contexts/AppContext';
import { BookOpen, Upload, Trash2, Plus, FileText, ArrowLeft } from 'lucide-react';

interface KnowledgePageProps {
  onBack: () => void;
  onImport: () => void;
}

export function KnowledgePage({ onBack, onImport }: KnowledgePageProps) {
  const { state, dispatch, deleteKnowledgeItem } = useApp();
  // Using knowledge list from context
  const [activeTab, setActiveTab] = useState<'all' | 'official' | 'personal'>('all');

  const officialKbs = state.knowledgeList.filter(k => k.type === 'official');
  const personalKbs = state.knowledgeList.filter(k => k.type === 'personal');
  const displayed = activeTab === 'official' ? officialKbs
    : activeTab === 'personal' ? personalKbs
    : state.knowledgeList;

  const handleDelete = (id: string) => {
    deleteKnowledgeItem(id);
  };

  return (
    <div className="flex flex-col h-full bg-white">
      {/* Header */}
      <div className="border-b border-gray-200 px-6 py-4">
        <div className="flex items-center gap-3 max-w-4xl mx-auto">
          <button onClick={onBack} className="p-2 rounded-lg hover:bg-gray-100 text-gray-500 transition-colors">
            <ArrowLeft size={18} />
          </button>
          <div className="w-8 h-8 bg-indigo-100 rounded-lg flex items-center justify-center">
            <BookOpen size={16} className="text-indigo-600" />
          </div>
          <h1 className="text-lg font-semibold text-gray-900 flex-1">知识库管理</h1>
          <button
            onClick={onImport}
            className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-xl transition-colors shadow-sm"
          >
            <Plus size={16} />
            导入知识库
          </button>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 mt-4 max-w-4xl mx-auto">
          {(['all', 'official', 'personal'] as const).map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-3 py-1.5 text-xs rounded-lg transition-colors ${
                activeTab === tab
                  ? 'bg-indigo-100 text-indigo-700 font-medium'
                  : 'text-gray-500 hover:bg-gray-100'
              }`}
            >
              {tab === 'all' ? `全部 (${state.knowledgeList.length})`
                : tab === 'official' ? `官方 (${officialKbs.length})`
                : `个人 (${personalKbs.length})`}
            </button>
          ))}
        </div>
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-4xl mx-auto">
          {displayed.length === 0 ? (
            <div className="text-center py-20">
              <FileText size={40} className="mx-auto mb-3 text-gray-300" />
              <p className="text-gray-400 text-sm">暂无知识库</p>
              <button onClick={onImport} className="mt-3 text-sm text-indigo-600 hover:text-indigo-700">
                + 导入知识库
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {displayed.map((kb) => {
                const isSelected = state.selectedKnowledge.includes(kb.id);
                return (
                  <div
                    key={kb.id}
                    className={`relative group rounded-xl border-2 p-4 cursor-pointer transition-all ${
                      isSelected
                        ? 'border-indigo-400 bg-indigo-50 shadow-sm'
                        : 'border-gray-200 hover:border-gray-300 bg-white hover:shadow-sm'
                    }`}
                    onClick={() => dispatch({ type: 'TOGGLE_KNOWLEDGE_SELECTION', id: kb.id })}
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div className="w-9 h-9 rounded-lg flex items-center justify-center shrink-0 ${
                        kb.type === 'official' ? 'bg-blue-100' : 'bg-amber-100'
                      }">
                        {kb.type === 'official'
                          ? <BookOpen size={16} className="text-blue-600" />
                          : <Upload size={16} className="text-amber-600" />}
                      </div>
                      {isSelected && (
                        <span className="w-5 h-5 rounded-full bg-indigo-500 flex items-center justify-center">
                          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3">
                            <path d="M20 6L9 17l-5-5" />
                          </svg>
                        </span>
                      )}
                    </div>
                    <h3 className="text-sm font-medium text-gray-800 mb-1 pr-6">{kb.name}</h3>
                    <p className="text-xs text-gray-400 line-clamp-2">{kb.description}</p>
                    <div className="flex items-center gap-2 mt-3">
                      <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                        kb.type === 'official' ? 'bg-blue-100 text-blue-600' : 'bg-amber-100 text-amber-600'
                      }`}>
                        {kb.type === 'official' ? '官方' : '个人'}
                      </span>
                      {kb.file_type && <span className="text-[10px] text-gray-400">{kb.file_type}</span>}
                    </div>
                    {kb.type === 'personal' && (
                      <button
                        onClick={(e) => { e.stopPropagation(); handleDelete(kb.id); }}
                        className="absolute top-3 right-3 opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-red-100 text-gray-400 hover:text-red-500 transition-all"
                      >
                        <Trash2 size={12} />
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
