export interface AFHClientOptions {
  baseUrl?: string;
  apiPrefix?: string;
  apiKey?: string;
  headers?: HeadersInit;
  fetch?: typeof fetch;
}

export interface RequestOptions {
  signal?: AbortSignal;
  headers?: HeadersInit;
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

export interface LlmApiConfigInput {
  name: string;
  model: string;
  base_url: string;
  api_key?: string;
  enabled: boolean;
  sort_order: number;
}

export interface CreateTaskResult {
  task_id: string;
  created_at: string;
  project_id: string;
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
  messages: ChatMessage[];
}

export interface ChatMessage {
  role: "user" | "agent";
  content: string;
  timestamp: string;
  metadata?: ChatMetadata;
}

export interface ChatMetadata {
  checklist?: ChecklistItem[];
  risks?: RiskItem[];
  needs_clarification?: string[];
  recommendations?: RecommendationItem[];
  priority_analysis?: string[];
  confirmation?: ConfirmationRequest;
  rag_chunks?: RagChunk[];
  knowledge_ids?: string[];
  task_summary?: TaskSummary;
  risk_control?: RiskControlMetadata;
  agent_id?: string;
  agent_name?: string;
  runtime_backend?: string;
  confidence?: "high" | "medium" | "low" | string;
  evidence_notes?: string[];
  follow_up_questions?: string[];
  timings_ms?: Record<string, number>;
  retrieval_mode?: string;
  retrieval_backend?: string;
  gpu_mode?: string;
  semantic_error?: string;
  phase?: string;
}

export interface RiskControlMetadata {
  findings: RiskFinding[];
  should_block_actions: boolean;
  high_count: number;
}

export interface RiskFinding {
  code: string;
  description: string;
  severity: "high" | "medium" | "low" | string;
  suggestion?: string;
  source?: string;
  product_name?: string | null;
  sku_id?: string | null;
  metadata?: Record<string, unknown>;
}

export interface ChecklistItem {
  condition: string;
  priority: "high" | "medium" | "low";
  detail?: string;
  checked?: boolean;
}

export interface RiskItem {
  description: string;
  severity: "high" | "medium";
}

export interface RecommendationItem {
  sku_id: string;
  product_name: string;
  priority: "high" | "medium" | "low";
  score: number;
  reason: string;
}

export interface ConfirmationRequest {
  required?: boolean;
  status?: "confirmed" | "cancelled" | string;
  question?: string;
  confirm_label?: string;
  revise_label?: string;
  recommended_skus?: string[];
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

export interface SkuProduct {
  sku_id: string;
  product_name: string;
  brand: string;
  category_l1: string;
  category_l2: string;
  pricing_model: string;
  weight_g: number | null;
  purity: string | null;
  tag_price_rmb: number;
  list_price_rmb: number | null;
  last_30d_min_price: number | null;
  last_90d_min_price: number | null;
  stock: number;
  last_90d_sales: number;
  review_rate: number;
  return_rate: number;
  certificate_ids: string[];
  active_campaigns: string[];
  [key: string]: unknown;
}

export interface ProductsResult {
  products: SkuProduct[];
  categories: string[];
  total: number;
}

export interface KnowledgeItem {
  id: string;
  name: string;
  type: "official" | "personal";
  description: string;
  created_at?: string;
  file_type?: string;
  file_count?: number;
  chunk_count?: number;
  embedding_backend?: string;
}

export interface UploadKnowledgeResult {
  id: string;
  name: string;
  files_indexed?: number;
  files_skipped?: number;
  chunks_added?: number;
  chunks_total?: number;
  embedding_backend?: string;
  errors?: string[];
}

export interface SummaryResult {
  title: string;
  overview?: string;
  rule_points: string[];
  recommendations: { item: string; reason: string }[];
  final_selection?: unknown[];
  selection_reasons?: string[];
  attention_items?: string[];
  confirmed_listing?: unknown[];
  checks: { name: string; status: string }[];
  risks: string[];
}

export interface ChatStreamRequest {
  task_id: string;
  message: string;
  knowledge_ids?: string[];
  agent_id?: string;
}

export interface StreamEvent {
  type:
    | "text"
    | "checklist"
    | "risks"
    | "clarification"
    | "recommendations"
    | "priority_analysis"
    | "confirmation"
    | "rag_chunks"
    | "agent_state"
    | "done";
  content?: string;
  items?: unknown[];
  item?: unknown;
}

export interface StreamChatOptions extends RequestOptions {
  onEvent?: (event: StreamEvent) => void;
  onText?: (text: string) => void;
  onRagChunks?: (chunks: RagChunk[]) => void;
}

export interface StreamChatResult {
  events: StreamEvent[];
  text: string;
  rag_chunks: RagChunk[];
}
