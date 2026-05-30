/* API service for backend communication */
import type { AgentLibraryItem, HistoryItem, HistoryDetail, KnowledgeItem, LlmApiConfig, ProjectItem, StreamEvent } from '../types';

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
export async function createTask(projectId: string = 'default'): Promise<{ task_id: string; created_at: string; project_id: string }> {
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
  overview?: string;
  agents?: string[];
  evidence_notes: string[];
  follow_up_questions: string[];
  rag_sources: { source_file: string; kb_id: string; snippet: string }[];
}> {
  return request(`/history/${taskId}/summarize`, { method: 'POST' });
}

export async function summarizeProject(projectId: string): Promise<{
  title: string;
  overview?: string;
  agents?: string[];
  evidence_notes: string[];
  follow_up_questions: string[];
  rag_sources: { source_file: string; kb_id: string; snippet: string }[];
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

export async function getLlmApiConfigs(): Promise<LlmApiConfig[]> {
  return request('/llm/configs');
}

export async function createLlmApiConfig(config: {
  name: string;
  model: string;
  base_url: string;
  api_key: string;
  enabled: boolean;
  sort_order: number;
}): Promise<{ success: boolean; config: LlmApiConfig }> {
  return request('/llm/configs', { method: 'POST', body: JSON.stringify(config) });
}

export async function updateLlmApiConfig(id: string, config: {
  name: string;
  model: string;
  base_url: string;
  api_key?: string;
  enabled: boolean;
  sort_order: number;
}): Promise<{ success: boolean; config: LlmApiConfig }> {
  return request(`/llm/configs/${encodeURIComponent(id)}`, { method: 'PUT', body: JSON.stringify(config) });
}

export async function deleteLlmApiConfig(id: string): Promise<{ success: boolean }> {
  return request(`/llm/configs/${encodeURIComponent(id)}`, { method: 'DELETE' });
}

/* Agents */
export async function getAgents(): Promise<AgentLibraryItem[]> {
  const data = await request<AgentLibraryItem[] | { agents?: AgentLibraryItem[] }>('/agents');
  return Array.isArray(data) ? data : data.agents ?? [];
}

/* Knowledge */
export async function getOfficialKnowledge(): Promise<KnowledgeItem[]> {
  return request('/knowledge/official');
}

export async function getPersonalKnowledge(): Promise<KnowledgeItem[]> {
  return request('/knowledge/personal');
}

export async function uploadKnowledge(name: string, content: string, files: File[] = []): Promise<{ id: string }> {
  const formData = new FormData();
  formData.append('name', name);
  formData.append('content', content);
  files.forEach((file) => formData.append('files', file, file.name));
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
  agentId: string,
  onEvent: (event: StreamEvent) => void,
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
        agent_id: agentId,
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
