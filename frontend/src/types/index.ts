/* Type definitions for the application */

export interface Message {
  role: 'user' | 'agent';
  content: string;
  timestamp: string;
  metadata?: {
    rag_chunks?: RagChunk[];
    knowledge_ids?: string[];
    agent_id?: string;
    agent_name?: string;
    runtime_backend?: string;
    confidence?: 'high' | 'medium' | 'low' | string;
    evidence_notes?: string[];
    follow_up_questions?: string[];
    timings_ms?: Record<string, number>;
    retrieval_mode?: string;
    retrieval_backend?: string;
    gpu_mode?: string;
    semantic_error?: string;
  };
}

export interface RagChunk {
  kb_id: string;
  source_file: string;
  score: number | null;
  dense_score?: number | null;
  bm25_score?: number | null;
  rrf_score?: number | null;
  snippet: string;
}

export interface HistoryItem {
  task_id: string;
  title: string;
  created_at: string;
  message_count: number;
  project_id?: string;
}

export interface HistoryDetail {
  task_id: string;
  title: string;
  created_at: string;
  messages: Message[];
}

export interface KnowledgeItem {
  id: string;
  name: string;
  type: 'official' | 'personal';
  description: string;
  created_at?: string;
  file_type?: string;
}

export interface AgentSpec {
  id: string;
  name: string;
  scenario: string;
  description: string;
  capabilities: string[];
  suggested_knowledge: string[];
  tools: string[];
  output_modes: string[];
  risk_controls: string[];
  orchestration_goal?: string;
  response_style?: string;
}

export type AgentLibraryItem = AgentSpec;

export interface StreamEvent {
  type: 'text' | 'rag_chunks' | 'agent_state' | 'done';
  content?: string;
  items?: RagChunk[];
  item?: Record<string, unknown>;
}

export interface ProjectItem {
  id: string;
  name: string;
  created_at: string;
}

export interface LlmApiConfig {
  id: string;
  name: string;
  model: string;
  base_url: string;
  enabled: boolean;
  sort_order: number;
  last_status: string;
  last_error: string;
  api_key_masked: string;
  created_at: string;
  updated_at: string;
}

export interface AppState {
  currentTaskId: string | null;
  currentProjectId: string;
  messages: Message[];
  history: HistoryItem[];
  projects: ProjectItem[];
  knowledgeList: KnowledgeItem[];
  selectedKnowledge: string[];
  agentList: AgentLibraryItem[];
  selectedAgentId: string;
  isLoading: boolean;
  streamingText: string;
  isSidebarOpen: boolean;
  error: string | null;
}
