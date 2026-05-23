/* Global state management */
import React, { createContext, useContext, useReducer, useCallback, useRef, type ReactNode } from 'react';
import type { AppState, Message, HistoryItem, KnowledgeItem, ProjectItem } from '../types';
import * as api from '../services/api';

type Action =
  | { type: 'SET_CURRENT_TASK'; taskId: string }
  | { type: 'SET_MESSAGES'; messages: Message[] }
  | { type: 'ADD_MESSAGE'; message: Message }
  | { type: 'UPDATE_LAST_AGENT_MESSAGE'; content: string; metadata?: Record<string, unknown> }
  | { type: 'SET_HISTORY'; history: HistoryItem[] }
  | { type: 'SET_KNOWLEDGE'; knowledge: KnowledgeItem[] }
  | { type: 'TOGGLE_KNOWLEDGE_SELECTION'; id: string }
  | { type: 'SET_LOADING'; loading: boolean }
  | { type: 'SET_STREAMING_TEXT'; text: string }
  | { type: 'APPEND_STREAMING_TEXT'; text: string }
  | { type: 'TOGGLE_SIDEBAR' }
  | { type: 'RESET_CHAT' }
  | { type: 'SET_ERROR'; error: string | null }
  | { type: 'SET_PROJECTS'; projects: ProjectItem[] }
  | { type: 'SET_CURRENT_PROJECT'; projectId: string };

const initialState: AppState = {
  currentTaskId: null,
  currentProjectId: 'default',
  messages: [],
  history: [],
  projects: [],
  knowledgeList: [],
  selectedKnowledge: [],
  isLoading: false,
  streamingText: '',
  isSidebarOpen: true,
  error: null,
};

function reducer(state: AppState, action: Action): AppState {
  switch (action.type) {
    case 'SET_CURRENT_TASK':
      return { ...state, currentTaskId: action.taskId };
    case 'SET_MESSAGES':
      return { ...state, messages: action.messages };
    case 'ADD_MESSAGE':
      return { ...state, messages: [...state.messages, action.message] };
    case 'UPDATE_LAST_AGENT_MESSAGE': {
      const messages = [...state.messages];
      const lastIdx = messages.length - 1;
      if (lastIdx >= 0 && messages[lastIdx].role === 'agent') {
        messages[lastIdx] = {
          ...messages[lastIdx],
          content: action.content,
          metadata: { ...messages[lastIdx].metadata, ...action.metadata },
        };
      }
      return { ...state, messages };
    }
    case 'SET_HISTORY':
      return { ...state, history: action.history };
    case 'SET_KNOWLEDGE':
      return { ...state, knowledgeList: action.knowledge };
    case 'TOGGLE_KNOWLEDGE_SELECTION': {
      const exists = state.selectedKnowledge.includes(action.id);
      return {
        ...state,
        selectedKnowledge: exists
          ? state.selectedKnowledge.filter((k) => k !== action.id)
          : [...state.selectedKnowledge, action.id],
      };
    }
    case 'SET_LOADING':
      return { ...state, isLoading: action.loading };
    case 'SET_STREAMING_TEXT':
      return { ...state, streamingText: action.text };
    case 'APPEND_STREAMING_TEXT':
      return { ...state, streamingText: state.streamingText + action.text };
    case 'TOGGLE_SIDEBAR':
      return { ...state, isSidebarOpen: !state.isSidebarOpen };
    case 'SET_ERROR':
      return { ...state, error: action.error };
    case 'SET_PROJECTS':
      return { ...state, projects: action.projects };
    case 'SET_CURRENT_PROJECT':
      return { ...state, currentProjectId: action.projectId };
    case 'RESET_CHAT':
      return { ...state, messages: [], streamingText: '', isLoading: false, currentTaskId: null };
    default:
      return state;
  }
}

interface AppContextType {
  state: AppState;
  dispatch: React.Dispatch<Action>;
  startNewTask: () => Promise<void>;
  loadHistory: () => Promise<void>;
  loadKnowledge: () => Promise<void>;
  loadProjects: () => Promise<void>;
  switchProject: (projectId: string) => Promise<void>;
  createNewProject: (name: string) => Promise<void>;
  sendMessage: (message: string) => Promise<void>;
  selectTask: (taskId: string) => Promise<void>;
  deleteTaskHistory: (taskId: string) => Promise<void>;
  uploadNewKnowledge: (name: string, content: string) => Promise<void>;
  renameTask: (taskId: string, name: string) => Promise<void>;
  renameProject: (projectId: string, name: string) => Promise<void>;
}

const AppContext = createContext<AppContextType | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState);
  const taskIdRef = useRef<string | null>(null);

  const startNewTask = useCallback(async () => {
    dispatch({ type: 'SET_LOADING', loading: true });
    try {
      const result = await api.createTask(state.currentProjectId);
      taskIdRef.current = result.task_id;
      dispatch({ type: 'SET_CURRENT_TASK', taskId: result.task_id });
      dispatch({ type: 'RESET_CHAT' });
      dispatch({ type: 'SET_CURRENT_TASK', taskId: result.task_id });
    } catch (err) {
      console.error('Failed to create task:', err);
    } finally {
      dispatch({ type: 'SET_LOADING', loading: false });
    }
  }, [state.currentProjectId]);

  const loadHistory = useCallback(async () => {
    try {
      const history = await api.getHistory(state.currentProjectId);
      dispatch({ type: 'SET_HISTORY', history });
    } catch (err) {
      console.error('Failed to load history:', err);
    }
  }, [state.currentProjectId]);

  const loadProjects = useCallback(async () => {
    try {
      const projects = await api.getProjects();
      dispatch({ type: 'SET_PROJECTS', projects });
    } catch (err) {
      console.error('Failed to load projects:', err);
    }
  }, []);

  const switchProject = useCallback(async (projectId: string) => {
    dispatch({ type: 'SET_CURRENT_PROJECT', projectId });
    dispatch({ type: 'RESET_CHAT' });
    // Reload history for the new project
    try {
      const history = await api.getHistory(projectId);
      dispatch({ type: 'SET_HISTORY', history });
    } catch (err) {
      console.error('Failed to load history:', err);
    }
  }, []);

  const createNewProject = useCallback(async (name: string) => {
    try {
      const proj = await api.createProject(name);
      await loadProjects();
      await switchProject(proj.id);
    } catch (err) {
      console.error('Failed to create project:', err);
    }
  }, [loadProjects, switchProject]);

  const loadKnowledge = useCallback(async () => {
    try {
      const [official, personal] = await Promise.all([
        api.getOfficialKnowledge(),
        api.getPersonalKnowledge(),
      ]);
      dispatch({ type: 'SET_KNOWLEDGE', knowledge: [...official, ...personal] });
    } catch (err) {
      console.error('Failed to load knowledge:', err);
    }
  }, []);

  const sendMessage = useCallback(
    async (message: string) => {
      // Clear previous errors
      dispatch({ type: 'SET_ERROR', error: null });

      try {
        // Ensure we have a task
        if (!state.currentTaskId) {
          const result = await api.createTask(state.currentProjectId);
          taskIdRef.current = result.task_id;
          dispatch({ type: 'SET_CURRENT_TASK', taskId: result.task_id });
        }

        const taskId = state.currentTaskId || taskIdRef.current!;

        // Add user message
        dispatch({
          type: 'ADD_MESSAGE',
          message: {
            role: 'user',
            content: message,
            timestamp: new Date().toISOString(),
          },
        });

        // Add placeholder agent message
        dispatch({
          type: 'ADD_MESSAGE',
          message: {
            role: 'agent',
            content: '',
            timestamp: new Date().toISOString(),
          },
        });

        dispatch({ type: 'SET_LOADING', loading: true });

        let streamedText = '';
        let agentMetadata: Record<string, unknown> | undefined;

        await api.streamChat(
          taskId,
          message,
          state.selectedKnowledge,
          (event) => {
            if (event.type === 'text' && event.content) {
              streamedText += event.content;
              dispatch({ type: 'UPDATE_LAST_AGENT_MESSAGE', content: streamedText });
            } else if (event.type === 'checklist' && event.items) {
              agentMetadata = { ...agentMetadata, checklist: event.items };
              dispatch({
                type: 'UPDATE_LAST_AGENT_MESSAGE',
                content: streamedText,
                metadata: { checklist: event.items },
              });
            } else if (event.type === 'risks' && event.items) {
              agentMetadata = { ...agentMetadata, risks: event.items };
              dispatch({
                type: 'UPDATE_LAST_AGENT_MESSAGE',
                content: streamedText,
                metadata: { risks: event.items },
              });
            } else if (event.type === 'clarification' && event.items) {
              agentMetadata = { ...agentMetadata, needs_clarification: event.items };
              dispatch({
                type: 'UPDATE_LAST_AGENT_MESSAGE',
                content: streamedText,
                metadata: { needs_clarification: event.items },
              });
            }
          },
          async () => {
            // onDone — persist agent response to backend
            dispatch({ type: 'SET_LOADING', loading: false });
            try {
              await api.saveMessage(taskId, 'agent', streamedText, agentMetadata);
            } catch (e) {
              console.error('Failed to save agent message:', e);
            }
            loadHistory();
          },
          (err) => {
            // onError
            console.error('Stream error:', err);
            dispatch({ type: 'SET_ERROR', error: err.message || '对话请求失败，请检查后端是否运行' });
            dispatch({ type: 'SET_LOADING', loading: false });
          },
        );
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : '网络请求失败，请确保后端服务正在运行';
        console.error('sendMessage error:', message);
        dispatch({ type: 'SET_ERROR', error: message });
        dispatch({ type: 'SET_LOADING', loading: false });
      }
    },
    [state.currentTaskId, state.selectedKnowledge, loadHistory],
  );

  const selectTask = useCallback(async (taskId: string) => {
    dispatch({ type: 'SET_LOADING', loading: true });
    try {
      const detail = await api.getHistoryDetail(taskId);
      taskIdRef.current = taskId;
      dispatch({ type: 'SET_CURRENT_TASK', taskId });
      dispatch({ type: 'SET_MESSAGES', messages: detail.messages });
    } catch (err) {
      console.error('Failed to load task:', err);
    } finally {
      dispatch({ type: 'SET_LOADING', loading: false });
    }
  }, []);

  const deleteTaskHistory = useCallback(
    async (taskId: string) => {
      await api.deleteHistory(taskId);
      if (state.currentTaskId === taskId) {
        dispatch({ type: 'RESET_CHAT' });
      }
      await loadHistory();
    },
    [state.currentTaskId, loadHistory],
  );

  const uploadNewKnowledge = useCallback(
    async (name: string, content: string) => {
      await api.uploadKnowledge(name, content);
      await loadKnowledge();
    },
    [loadKnowledge],
  );

  const renameTask = useCallback(
    async (taskId: string, name: string) => {
      await api.renameTask(taskId, name);
      await loadHistory();
    },
    [loadHistory],
  );

  const renameProject = useCallback(
    async (projectId: string, name: string) => {
      await api.renameProject(projectId, name);
      await loadProjects();
    },
    [loadProjects],
  );

  return (
    <AppContext.Provider
      value={{
        state,
        dispatch,
        startNewTask,
        loadHistory,
        loadKnowledge,
        loadProjects,
        switchProject,
        createNewProject,
        sendMessage,
        selectTask,
        deleteTaskHistory,
        uploadNewKnowledge,
        renameTask,
        renameProject,
      }}
    >
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useApp must be used within AppProvider');
  }
  return context;
}
