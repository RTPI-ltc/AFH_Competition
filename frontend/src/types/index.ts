/* Type definitions for the application */

export interface Message {
  role: 'user' | 'agent';
  content: string;
  timestamp: string;
  metadata?: {
    checklist?: CheckListItem[];
    risks?: RiskItem[];
    needs_clarification?: string[];
  };
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
  type: 'text' | 'checklist' | 'risks' | 'clarification' | 'done';
  content?: string;
  items?: CheckListItem[] | RiskItem[] | string[];
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
