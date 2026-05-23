/* API service for backend communication */
import type { HistoryItem, HistoryDetail, KnowledgeItem, ProjectItem } from '../types';

const BASE = '/api';

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Request failed' }));
    throw new Error(err.detail || 'Request failed');
  }
  return res.json();
}

/* Task */
export async function createTask(projectId: string = 'default'): Promise<{ task_id: string; created_at: string }> {
  return request(`/task/new?project_id=${encodeURIComponent(projectId)}`, { method: 'POST' });
}

/* History */
export async function getHistory(projectId?: string): Promise<HistoryItem[]> {
  const q = projectId ? `?project_id=${encodeURIComponent(projectId)}` : '';
  return request(`/history${q}`);
}

export async function getHistoryDetail(taskId: string): Promise<HistoryDetail> {
  return request(`/history/${taskId}`);
}

export async function deleteHistory(taskId: string): Promise<void> {
  return request(`/history/${taskId}`, { method: 'DELETE' });
}

export async function saveMessage(taskId: string, role: string, content: string, metadata?: Record<string, unknown>): Promise<void> {
  return request(`/history/${taskId}/message`, {
    method: 'POST',
    body: JSON.stringify({ role, content, metadata }),
  });
}

export async function summarizeTask(taskId: string): Promise<{
  title: string;
  rule_points: string[];
  recommendations: { item: string; reason: string }[];
  checks: { name: string; status: string }[];
  risks: string[];
}> {
  return request(`/history/${taskId}/summarize`, { method: 'POST' });
}

export async function summarizeProject(projectId: string): Promise<{
  title: string;
  rule_points: string[];
  recommendations: { item: string; reason: string }[];
  checks: { name: string; status: string }[];
  risks: string[];
}> {
  return request(`/projects/${projectId}/summarize`, { method: 'POST' });
}

/* Projects */
export async function getProjects(): Promise<ProjectItem[]> {
  return request('/projects');
}

export async function createProject(name: string): Promise<ProjectItem> {
  return request(`/projects?name=${encodeURIComponent(name)}`, { method: 'POST' });
}

export async function renameProject(id: string, name: string): Promise<void> {
  return request(`/projects/${id}/rename?name=${encodeURIComponent(name)}`, { method: 'PUT' });
}

export async function renameTask(taskId: string, name: string): Promise<void> {
  return request(`/history/${taskId}/rename?name=${encodeURIComponent(name)}`, { method: 'PUT' });
}

export async function getProducts(category?: string, search?: string): Promise<{
  products: SkuProduct[];
  categories: string[];
  total: number;
}> {
  const params = new URLSearchParams();
  if (category) params.set('category_l1', category);
  if (search) params.set('search', search);
  return request(`/products?${params.toString()}`);
}

export async function addProduct(product: Record<string, unknown>): Promise<{ success: boolean; product: SkuProduct }> {
  return request('/products', { method: 'POST', body: JSON.stringify(product) });
}

export async function deleteProduct(skuId: string): Promise<{ success: boolean }> {
  return request(`/products/${encodeURIComponent(skuId)}`, { method: 'DELETE' });
}

export interface SkuProduct {
  sku_id: string; product_name: string; brand: string;
  category_l1: string; category_l2: string; pricing_model: string;
  weight_g: number | null; purity: string | null;
  gem_carat: number | null; gem_color: string | null; gem_clarity: string | null; gem_cut: string | null;
  tag_price_rmb: number; list_price_rmb: number | null;
  last_30d_min_price: number | null; last_90d_min_price: number | null; last_365d_min_price: number | null;
  stock: number; last_90d_sales: number; review_rate: number; return_rate: number;
  new_product: boolean; certificate_ids: string[];
  factory_id: string; lead_time_days: number; active_campaigns: string[];
}

/* Knowledge */
export async function getOfficialKnowledge(): Promise<KnowledgeItem[]> {
  return request('/knowledge/official');
}

export async function getPersonalKnowledge(): Promise<KnowledgeItem[]> {
  return request('/knowledge/personal');
}

export async function uploadKnowledge(name: string, content: string): Promise<{ id: string }> {
  const formData = new FormData();
  formData.append('name', name);
  formData.append('content', content);
  const res = await fetch(`${BASE}/knowledge/upload`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) throw new Error('Upload failed');
  return res.json();
}

export async function deleteKnowledge(id: string): Promise<void> {
  return request(`/knowledge/${id}`, { method: 'DELETE' });
}

/* Chat SSE Stream */
export async function streamChat(
  taskId: string,
  message: string,
  knowledgeIds: string[],
  onEvent: (event: { type: string; content?: string; items?: unknown[] }) => void,
  onDone: () => void,
  onError: (err: Error) => void,
) {
  try {
    const res = await fetch(`${BASE}/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        task_id: taskId,
        message,
        knowledge_ids: knowledgeIds,
      }),
    });

    if (!res.ok) {
      throw new Error('Chat request failed');
    }

    const reader = res.body?.getReader();
    if (!reader) throw new Error('No response body');

    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        const trimmed = line.trim();
        if (trimmed.startsWith('data: ')) {
          try {
            const data = JSON.parse(trimmed.slice(6));
            if (data.type === 'done') {
              onDone();
              return;
            }
            onEvent(data);
          } catch {
            // skip invalid JSON lines
          }
        }
      }
    }
    onDone();
  } catch (err) {
    onError(err instanceof Error ? err : new Error('Unknown error'));
  }
}
