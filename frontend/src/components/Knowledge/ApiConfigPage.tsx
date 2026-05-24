import { useEffect, useMemo, useState } from 'react';
import { ArrowLeft, CheckCircle2, KeyRound, Plus, Trash2 } from 'lucide-react';
import type { LlmApiConfig } from '../../types';
import {
  createLlmApiConfig,
  deleteLlmApiConfig,
  getLlmApiConfigs,
  updateLlmApiConfig,
} from '../../services/api';

interface ApiConfigPageProps {
  onBack: () => void;
}

const emptyForm = {
  name: '阿里云 Qwen',
  model: 'qwen-plus',
  base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
  api_key: '',
  enabled: true,
  sort_order: 100,
};

export function ApiConfigPage({ onBack }: ApiConfigPageProps) {
  const [configs, setConfigs] = useState<LlmApiConfig[]>([]);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const editing = useMemo(
    () => configs.find((item) => item.id === editingId) || null,
    [configs, editingId],
  );

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      setConfigs(await getLlmApiConfigs());
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const startEdit = (item: LlmApiConfig) => {
    setEditingId(item.id);
    setForm({
      name: item.name,
      model: item.model,
      base_url: item.base_url,
      api_key: '',
      enabled: item.enabled,
      sort_order: item.sort_order,
    });
  };

  const resetForm = () => {
    setEditingId(null);
    setForm(emptyForm);
  };

  const submit = async () => {
    setLoading(true);
    setError('');
    try {
      if (editingId) {
        await updateLlmApiConfig(editingId, {
          name: form.name,
          model: form.model,
          base_url: form.base_url,
          api_key: form.api_key || undefined,
          enabled: form.enabled,
          sort_order: Number(form.sort_order) || 100,
        });
      } else {
        await createLlmApiConfig({
          name: form.name,
          model: form.model,
          base_url: form.base_url,
          api_key: form.api_key,
          enabled: form.enabled,
          sort_order: Number(form.sort_order) || 100,
        });
      }
      resetForm();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : '保存失败');
    } finally {
      setLoading(false);
    }
  };

  const remove = async (id: string) => {
    setLoading(true);
    setError('');
    try {
      await deleteLlmApiConfig(id);
      if (editingId === id) resetForm();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : '删除失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex-1 overflow-y-auto bg-white">
      <div className="max-w-5xl mx-auto px-8 py-8">
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-3">
            <button
              onClick={onBack}
              className="p-2 rounded-lg hover:bg-gray-100 text-gray-500"
              title="返回对话"
            >
              <ArrowLeft size={18} />
            </button>
            <div>
              <h2 className="text-2xl font-semibold text-gray-900">API 配置</h2>
              <p className="text-sm text-gray-500 mt-1">
                Chat 会按排序从上到下尝试，失败后自动切换到下一组配置。
              </p>
            </div>
          </div>
          <button
            onClick={resetForm}
            className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-indigo-600 text-white text-sm hover:bg-indigo-700"
          >
            <Plus size={16} />
            新增配置
          </button>
        </div>

        {error && (
          <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <div className="grid grid-cols-[1fr_360px] gap-6">
          <div className="border border-gray-200 rounded-xl overflow-hidden">
            <div className="grid grid-cols-[70px_1fr_130px_80px] gap-3 px-4 py-3 text-xs font-medium text-gray-500 bg-gray-50 border-b border-gray-200">
              <span>顺序</span>
              <span>配置</span>
              <span>状态</span>
              <span className="text-right">操作</span>
            </div>
            {configs.length === 0 && (
              <div className="px-4 py-10 text-center text-sm text-gray-400">
                暂无 API 配置
              </div>
            )}
            {configs.map((item) => (
              <div
                key={item.id}
                className={`grid grid-cols-[70px_1fr_130px_80px] gap-3 px-4 py-4 border-b border-gray-100 last:border-b-0 ${
                  editingId === item.id ? 'bg-indigo-50/40' : 'bg-white'
                }`}
              >
                <div className="text-sm text-gray-600">{item.sort_order}</div>
                <button className="text-left min-w-0" onClick={() => startEdit(item)}>
                  <div className="flex items-center gap-2">
                    <KeyRound size={15} className={item.enabled ? 'text-indigo-500' : 'text-gray-300'} />
                    <span className="text-sm font-medium text-gray-900 truncate">{item.name}</span>
                    {!item.enabled && <span className="text-[10px] text-gray-400">停用</span>}
                  </div>
                  <div className="text-xs text-gray-500 mt-1 truncate">
                    {item.model} · {item.base_url}
                  </div>
                  <div className="text-xs text-gray-400 mt-1">Key: {item.api_key_masked || '未配置'}</div>
                </button>
                <div className="text-xs">
                  <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full ${
                    item.last_status === 'ok'
                      ? 'bg-green-50 text-green-700'
                      : item.last_status === 'error'
                        ? 'bg-red-50 text-red-700'
                        : 'bg-gray-100 text-gray-500'
                  }`}>
                    <CheckCircle2 size={12} />
                    {item.last_status || 'untested'}
                  </span>
                  {item.last_error && <div className="text-red-500 mt-1 truncate">{item.last_error}</div>}
                </div>
                <div className="flex justify-end">
                  <button
                    onClick={() => void remove(item.id)}
                    disabled={loading}
                    className="p-2 text-gray-400 hover:text-red-600 disabled:opacity-50"
                    title="删除"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>
            ))}
          </div>

          <div className="border border-gray-200 rounded-xl p-5 h-fit">
            <h3 className="text-sm font-semibold text-gray-900 mb-4">
              {editing ? `编辑：${editing.name}` : '新增 API 配置'}
            </h3>
            <div className="space-y-4">
              <label className="block">
                <span className="text-xs text-gray-500">名称</span>
                <input
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  className="mt-1 w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </label>
              <label className="block">
                <span className="text-xs text-gray-500">模型名称</span>
                <input
                  value={form.model}
                  onChange={(e) => setForm({ ...form, model: e.target.value })}
                  placeholder="qwen-plus / deepseek-chat"
                  className="mt-1 w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </label>
              <label className="block">
                <span className="text-xs text-gray-500">Base URL</span>
                <input
                  value={form.base_url}
                  onChange={(e) => setForm({ ...form, base_url: e.target.value })}
                  placeholder="https://dashscope.aliyuncs.com/compatible-mode/v1"
                  className="mt-1 w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </label>
              <label className="block">
                <span className="text-xs text-gray-500">API Key</span>
                <input
                  value={form.api_key}
                  onChange={(e) => setForm({ ...form, api_key: e.target.value })}
                  type="password"
                  placeholder={editing ? '留空则保持原 Key' : 'sk-...'}
                  className="mt-1 w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </label>
              <div className="grid grid-cols-2 gap-3">
                <label className="block">
                  <span className="text-xs text-gray-500">排序</span>
                  <input
                    value={form.sort_order}
                    onChange={(e) => setForm({ ...form, sort_order: Number(e.target.value) })}
                    type="number"
                    className="mt-1 w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </label>
                <label className="flex items-end gap-2 pb-2 text-sm text-gray-600">
                  <input
                    checked={form.enabled}
                    onChange={(e) => setForm({ ...form, enabled: e.target.checked })}
                    type="checkbox"
                    className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                  />
                  启用
                </label>
              </div>
              <button
                onClick={() => void submit()}
                disabled={loading || !form.name || !form.model || !form.base_url || (!editingId && !form.api_key)}
                className="w-full rounded-lg bg-indigo-600 text-white py-2 text-sm font-medium hover:bg-indigo-700 disabled:opacity-50"
              >
                {loading ? '保存中...' : editing ? '保存修改' : '创建配置'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
