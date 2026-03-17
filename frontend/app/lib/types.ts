// Message and event types for the support agent chat UI

export type MessageRole = "user" | "assistant" | "system";

export interface ToolExecution {
  id: string;
  toolName: string;
  args?: Record<string, unknown>;
  result?: string;
  status: "running" | "complete" | "error";
  startedAt: number;
  completedAt?: number;
}

export interface AgentEvent {
  id: string;
  eventName: string;
  data?: Record<string, unknown>;
  timestamp: number;
}

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: number;
  toolExecutions?: ToolExecution[];
  agentEvents?: AgentEvent[];
  isStreaming?: boolean;
}

export interface Model {
  id: string;
  name: string;
}

// WebSocket events from the backend
export type ServerEvent =
  | { type: "assistant.message_delta"; content: string }
  | { type: "assistant.message"; content: string }
  | {
      type: "tool.execution_start";
      tool_name: string;
      args: Record<string, unknown>;
      tool_call_id?: string;
    }
  | {
      type: "tool.execution_complete";
      tool_name: string;
      result: string;
      tool_call_id?: string;
    }
  | {
      type: "agent.event";
      event_name: string;
      data?: Record<string, unknown>;
    }
  | { type: "session.idle" }
  | { type: "error"; message: string };

export interface ChatSession {
  sessionId: string;
  messages: ChatMessage[];
  isLoading: boolean;
}

// ---------------------------------------------------------------------------
// 基地局設置チェッカー types
// ---------------------------------------------------------------------------

export interface CheckItem {
  item: string;
  standard: string;
  current: string;
  status: "pass" | "fail" | "constraint";
}

export interface Alternative {
  name: string;
  coverage: string;
  cost_delta: string;
  timeline_delta: string;
}

export interface Source {
  type: "email" | "meeting" | "document";
  title: string;
  date: string;
  author: string;
  summary?: string;
  url?: string;
}

export interface CheckResult {
  verdict: "go" | "conditional_go" | "no_go";
  verdict_reason: string;
  checks: CheckItem[];
  alternatives: Alternative[];
  actions: string[];
  sources: Source[];
  coverage: {
    current: number;
    standard: number;
    alternative: number | null;
  };
}

export type LogEvent =
  | { type: "log"; message: string }
  | { type: "result"; data: CheckResult }
  | { type: "error"; message: string };

