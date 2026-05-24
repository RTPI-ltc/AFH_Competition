/* Type definitions for the application */

export interface Message {
  role: 'user' | 'agent';
  content: string;
  timestamp: string;
  metadata?: {
    checklist?: CheckListItem[];
    risks?: RiskItem[];
    needs_clarification?: string[];
    recommendations?: RecommendationItem[];
    priority_analysis?: string[];
    confirmation?: ConfirmationRequest;
    rag_chunks?: RagChunk[];
    knowledge_ids?: string[];
    task_summary?: TaskSummary;
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

export interface CheckListItem {
  condition: string;
  priority: 'high' | 'medium' | 'low';
  detail?: string;
  checked?: boolean;
}

export interface RiskItem {
  description: string;
  severity: 'high' | 'medium';
}

export interface RecommendationItem {
  sku_id: string;
  product_name: string;
  priority: 'high' | 'medium' | 'low';
  score: number;
  reason: string;
}

export interface TaskSummaryItem {
  product_name: string;
  status: string;
  notes: string;
  sku_id: string;
  category: string;
}

export interface TaskSummary {
  items: TaskSummaryItem[];
  total: number;
}

export interface ConfirmationRequest {
  required?: boolean;
  status?: 'confirmed' | 'cancelled' | string;
  question?: string;
  confirm_label?: string;
  revise_label?: string;
  recommended_skus?: string[];
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

export interface StreamEvent {
  type: 'text' | 'checklist' | 'risks' | 'clarification' | 'recommendations' | 'priority_analysis' | 'confirmation' | 'rag_chunks' | 'done';
  content?: string;
  items?: CheckListItem[] | RiskItem[] | RecommendationItem[] | RagChunk[] | string[];
  item?: ConfirmationRequest;
}

export interface ProjectItem {
  id: string;
  name: string;
  created_at: string;
}

export interface AppState {
  currentTaskId: string | null;
  currentProjectId: string;
  messages: Message[];
  history: HistoryItem[];
  projects: ProjectItem[];
  knowledgeList: KnowledgeItem[];
  selectedKnowledge: string[];
  isLoading: boolean;
  streamingText: string;
  isSidebarOpen: boolean;
  error: string | null;
}
