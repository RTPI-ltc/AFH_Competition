import type {
  AFHClientOptions,
  ChatStreamRequest,
  CreateTaskResult,
  HistoryDetail,
  HistoryItem,
  KnowledgeItem,
  LlmApiConfig,
  LlmApiConfigInput,
  ProductsResult,
  ProjectItem,
  RagChunk,
  RequestOptions,
  StreamChatOptions,
  StreamChatResult,
  StreamEvent,
  SummaryResult,
  UploadKnowledgeResult,
} from "./types";

type JsonBody = Record<string, unknown> | unknown[];

export class AFHApiError extends Error {
  constructor(message: string, readonly status: number, readonly detail: unknown) {
    super(message);
    this.name = "AFHApiError";
  }
}

export class AFHClient {
  private readonly baseUrl: string;
  private readonly apiPrefix: string;
  private readonly apiKey?: string;
  private readonly defaultHeaders?: HeadersInit;
  private readonly fetcher: typeof fetch;

  constructor(options: AFHClientOptions = {}) {
    this.baseUrl = (options.baseUrl ?? "").replace(/\/$/, "");
    this.apiPrefix = normalizePrefix(options.apiPrefix ?? "/api");
    this.apiKey = options.apiKey;
    this.defaultHeaders = options.headers;
    this.fetcher = options.fetch ?? globalThis.fetch;
    if (!this.fetcher) throw new Error("AFHClient requires a fetch implementation.");
  }

  health(options?: RequestOptions): Promise<{ status: string }> {
    return this.request("/health", requestOptions(options));
  }

  llmHealth(options?: RequestOptions): Promise<Record<string, unknown>> {
    return this.request("/llm/health", requestOptions(options));
  }

  listLlmApiConfigs(options?: RequestOptions): Promise<LlmApiConfig[]> {
    return this.request("/llm/configs", requestOptions(options));
  }

  createLlmApiConfig(config: LlmApiConfigInput & { api_key: string }, options?: RequestOptions): Promise<{ success: boolean; config: LlmApiConfig }> {
    return this.request("/llm/configs", {
      ...requestOptions(options),
      method: "POST",
      body: { ...config },
    });
  }

  updateLlmApiConfig(configId: string, config: LlmApiConfigInput, options?: RequestOptions): Promise<{ success: boolean; config: LlmApiConfig }> {
    return this.request(`/llm/configs/${encodeURIComponent(configId)}`, {
      ...requestOptions(options),
      method: "PUT",
      body: { ...config },
    });
  }

  deleteLlmApiConfig(configId: string, options?: RequestOptions): Promise<{ success: boolean }> {
    return this.request(`/llm/configs/${encodeURIComponent(configId)}`, {
      ...requestOptions(options),
      method: "DELETE",
    });
  }

  listProjects(options?: RequestOptions): Promise<ProjectItem[]> {
    return this.request("/projects", requestOptions(options));
  }

  createProject(name: string, options?: RequestOptions): Promise<ProjectItem> {
    return this.request(`/projects?name=${encodeURIComponent(name)}`, {
      ...requestOptions(options),
      method: "POST",
    });
  }

  renameProject(projectId: string, name: string, options?: RequestOptions): Promise<{ success: boolean }> {
    return this.request(`/projects/${encodeURIComponent(projectId)}/rename?name=${encodeURIComponent(name)}`, {
      ...requestOptions(options),
      method: "PUT",
    });
  }

  createTask(projectId = "default", options?: RequestOptions): Promise<CreateTaskResult> {
    return this.request(`/task/new?project_id=${encodeURIComponent(projectId)}`, {
      ...requestOptions(options),
      method: "POST",
    });
  }

  listHistory(projectId?: string, options?: RequestOptions): Promise<HistoryItem[]> {
    const query = projectId ? `?project_id=${encodeURIComponent(projectId)}` : "";
    return this.request(`/history${query}`, requestOptions(options));
  }

  getHistoryDetail(taskId: string, options?: RequestOptions): Promise<HistoryDetail> {
    return this.request(`/history/${encodeURIComponent(taskId)}`, requestOptions(options));
  }

  summarizeTask(taskId: string, options?: RequestOptions): Promise<SummaryResult> {
    return this.request(`/history/${encodeURIComponent(taskId)}/summarize`, {
      ...requestOptions(options),
      method: "POST",
    });
  }

  summarizeProject(projectId: string, options?: RequestOptions): Promise<SummaryResult> {
    return this.request(`/projects/${encodeURIComponent(projectId)}/summarize`, {
      ...requestOptions(options),
      method: "POST",
    });
  }

  listProducts(params: { category?: string; search?: string } = {}, options?: RequestOptions): Promise<ProductsResult> {
    const search = new URLSearchParams();
    if (params.category) search.set("category_l1", params.category);
    if (params.search) search.set("search", params.search);
    const query = search.toString();
    return this.request(`/products${query ? `?${query}` : ""}`, requestOptions(options));
  }

  addProduct(product: Record<string, unknown>, options?: RequestOptions): Promise<{ success: boolean; product: unknown }> {
    return this.request("/products", {
      ...requestOptions(options),
      method: "POST",
      body: product,
    });
  }

  deleteProduct(skuId: string, options?: RequestOptions): Promise<{ success: boolean }> {
    return this.request(`/products/${encodeURIComponent(skuId)}`, {
      ...requestOptions(options),
      method: "DELETE",
    });
  }

  listOfficialKnowledge(options?: RequestOptions): Promise<KnowledgeItem[]> {
    return this.request("/knowledge/official", requestOptions(options));
  }

  listPersonalKnowledge(options?: RequestOptions): Promise<KnowledgeItem[]> {
    return this.request("/knowledge/personal", requestOptions(options));
  }

  async uploadKnowledge(options: {
    name: string;
    content?: string;
    description?: string;
    files?: Array<Blob & { name?: string }>;
  } & RequestOptions): Promise<UploadKnowledgeResult> {
    const formData = new FormData();
    formData.append("name", options.name);
    if (options.description) formData.append("description", options.description);
    formData.append("content", options.content ?? "");
    for (const file of options.files ?? []) {
      formData.append("files", file, file.name ?? "attachment");
    }
    return this.request("/knowledge/upload", {
      ...requestOptions(options),
      method: "POST",
      formData,
    });
  }

  deleteKnowledge(knowledgeId: string, options?: RequestOptions): Promise<{ success: boolean }> {
    return this.request(`/knowledge/${encodeURIComponent(knowledgeId)}`, {
      ...requestOptions(options),
      method: "DELETE",
    });
  }

  async streamChat(request: ChatStreamRequest, options: StreamChatOptions = {}): Promise<StreamChatResult> {
    const response = await this.rawRequest("/chat/stream", {
      method: "POST",
      body: JSON.stringify({
        task_id: request.task_id,
        message: request.message,
        knowledge_ids: request.knowledge_ids ?? [],
        agent_id: request.agent_id,
      }),
      headers: {
        "Content-Type": "application/json",
        ...headersToObject(options.headers),
      },
      signal: options.signal,
    });

    const reader = response.body?.getReader();
    if (!reader) throw new Error("Chat stream response has no readable body.");

    const decoder = new TextDecoder();
    const events: StreamEvent[] = [];
    const ragChunks: RagChunk[] = [];
    let text = "";
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";
      for (const line of lines) {
        const event = parseSseLine(line);
        if (!event) continue;
        events.push(event);
        options.onEvent?.(event);
        if (event.type === "text" && event.content) {
          text += event.content;
          options.onText?.(event.content);
        }
        if (event.type === "rag_chunks") {
          const chunks = Array.isArray(event.items) ? (event.items as RagChunk[]) : [];
          ragChunks.push(...chunks);
          options.onRagChunks?.(chunks);
        }
        if (event.type === "done") return { events, text, rag_chunks: ragChunks };
      }
    }
    return { events, text, rag_chunks: ragChunks };
  }

  private async request<T>(
    path: string,
    init: RequestOptions & { method?: string; body?: JsonBody; formData?: FormData } = {},
  ): Promise<T> {
    const headers = init.formData ? init.headers : { "Content-Type": "application/json", ...headersToObject(init.headers) };
    const response = await this.rawRequest(path, {
      method: init.method ?? "GET",
      body: init.formData ?? (init.body === undefined ? undefined : JSON.stringify(init.body)),
      headers,
      signal: init.signal,
    });
    return response.json() as Promise<T>;
  }

  private async rawRequest(path: string, init: RequestInit): Promise<Response> {
    const response = await this.fetcher(this.url(path), {
      ...init,
      headers: this.headers(init.headers),
    });
    if (!response.ok) {
      const detail = await response.json().catch(() => undefined);
      throw new AFHApiError(errorMessage(detail, response.statusText), response.status, detail);
    }
    return response;
  }

  private url(path: string): string {
    return `${this.baseUrl}${this.apiPrefix}${path.startsWith("/") ? path : `/${path}`}`;
  }

  private headers(headers?: HeadersInit): HeadersInit {
    const merged: Record<string, string> = {};
    Object.assign(merged, headersToObject(this.defaultHeaders));
    if (this.apiKey) merged.Authorization = `Bearer ${this.apiKey}`;
    Object.assign(merged, headersToObject(headers));
    return merged;
  }
}

function normalizePrefix(prefix: string): string {
  const clean = prefix.trim();
  if (!clean || clean === "/") return "";
  return clean.startsWith("/") ? clean.replace(/\/$/, "") : `/${clean.replace(/\/$/, "")}`;
}

function requestOptions(options?: RequestOptions): RequestOptions {
  return options ?? {};
}

function headersToObject(source?: HeadersInit): Record<string, string> {
  const result: Record<string, string> = {};
  if (!source) return result;
  if (source instanceof Headers) {
    source.forEach((value, key) => {
      result[key] = value;
    });
    return result;
  }
  if (Array.isArray(source)) {
    for (const [key, value] of source) result[key] = value;
    return result;
  }
  return { ...source };
}

function errorMessage(detail: unknown, fallback: string): string {
  if (detail && typeof detail === "object" && "detail" in detail) {
    const message = (detail as { detail?: unknown }).detail;
    if (typeof message === "string") return message;
  }
  return fallback || "AFH API request failed";
}

function parseSseLine(line: string): StreamEvent | null {
  const trimmed = line.trim();
  if (!trimmed.startsWith("data: ")) return null;
  try {
    return JSON.parse(trimmed.slice(6)) as StreamEvent;
  } catch {
    return null;
  }
}
