"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { v4 as uuidv4 } from "uuid";
import { AgentEvent, ChatMessage, Model, ServerEvent, ToolExecution } from "@/app/lib/types";
import { createSession, deleteSession, fetchModels, connectWebSocket } from "@/app/lib/api";
import MessageList from "./MessageList";
import ModelSelector from "./ModelSelector";
import ApprovalReportPanel from "./ApprovalReportPanel";

// Pre-built trigger prompt for the municipality email demo flow
const MUNICIPALITY_TRIGGER_PROMPT =
  "A市から設置許可メールが到着しました。" +
  "Work IQを使って中村さんの自治体調整経緯、鈴木さんの設計制約、" +
  "スモールセルのコスト承認状況を収集し、承認レポートを生成してください。";

/** Extract the site-approval-report code block content from a message string. */
function extractApprovalReport(content: string): string | null {
  const startMarker = "```site-approval-report\n";
  const endMarker = "\n```";
  const startIdx = content.indexOf(startMarker);
  if (startIdx === -1) return null;
  const reportStart = startIdx + startMarker.length;
  const endIdx = content.indexOf(endMarker, reportStart);
  return endIdx !== -1
    ? content.slice(reportStart, endIdx)
    : content.slice(reportStart); // still streaming
}

export default function ChatInterface() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [models, setModels] = useState<Model[]>([]);
  const [selectedModel, setSelectedModel] = useState("gpt-4o");
  const [inputValue, setInputValue] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [approvalReport, setApprovalReport] = useState<string | null>(null);
  const [reportStreaming, setReportStreaming] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // -------------------------------------------------------------------------
  // Session management
  // -------------------------------------------------------------------------

  const initSession = useCallback(async () => {
    try {
      const id = await createSession();
      setSessionId(id);

      const ws = connectWebSocket(id);
      wsRef.current = ws;

      ws.onopen = () => console.log("WebSocket connected");
      ws.onerror = (e) => console.error("WebSocket error", e);
      ws.onclose = () => console.log("WebSocket closed");

      return ws;
    } catch (err) {
      console.error("Failed to init session", err);
    }
  }, []);

  useEffect(() => {
    fetchModels().then((m) => {
      setModels(m);
      if (m.length > 0) setSelectedModel(m[0].id);
    });

    let cleanupWs: WebSocket | null = null;
    let cleanupSessionId: string | null = null;

    initSession().then((ws) => {
      cleanupWs = ws ?? null;
    });

    return () => {
      cleanupWs?.close();
      if (cleanupSessionId) deleteSession(cleanupSessionId);
    };
  }, [initSession]);

  // Scan latest assistant message for approval report content
  useEffect(() => {
    const assistantMessages = messages.filter((m) => m.role === "assistant");
    if (assistantMessages.length === 0) return;
    const latest = assistantMessages[assistantMessages.length - 1];
    const extracted = extractApprovalReport(latest.content);
    if (extracted !== null) {
      setApprovalReport(extracted);
      setReportStreaming(latest.isStreaming ?? false);
    }
  }, [messages]);

  // -------------------------------------------------------------------------
  // Message streaming via WebSocket
  // -------------------------------------------------------------------------

  const sendMessage = useCallback(async (overridePrompt?: string) => {
    const prompt = overridePrompt ?? inputValue.trim();
    if (!prompt || isLoading || !wsRef.current) return;

    if (!overridePrompt) setInputValue("");
    setIsLoading(true);

    // Add user message
    const userMsg: ChatMessage = {
      id: uuidv4(),
      role: "user",
      content: prompt,
      timestamp: Date.now(),
    };
    setMessages((prev) => [...prev, userMsg]);

    // Prepare assistant message placeholder
    const assistantMsgId = uuidv4();
    const assistantMsg: ChatMessage = {
      id: assistantMsgId,
      role: "assistant",
      content: "",
      timestamp: Date.now(),
      toolExecutions: [],
      agentEvents: [],
      isStreaming: true,
    };
    setMessages((prev) => [...prev, assistantMsg]);

    // Track tool executions in progress
    const activeToolsById = new Map<string, ToolExecution>();
    const activeToolIdsByName = new Map<string, string[]>();

    const finalizeRunningTools = (fallbackResult?: string) => {
      setMessages((prev) =>
        prev.map((m) => {
          if (m.id !== assistantMsgId) return m;
          return {
            ...m,
            toolExecutions: (m.toolExecutions ?? []).map((tool) =>
              tool.status === "running"
                ? {
                    ...tool,
                    status: "complete",
                    completedAt: Date.now(),
                    result: tool.result ?? fallbackResult,
                  }
                : tool
            ),
          };
        })
      );
    };

    wsRef.current.onmessage = (event: MessageEvent) => {
      const data: ServerEvent = JSON.parse(event.data);

      switch (data.type) {
        case "assistant.message_delta":
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantMsgId
                ? { ...m, content: m.content + data.content, isStreaming: true }
                : m
            )
          );
          break;

        case "assistant.message":
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantMsgId
                ? { ...m, content: data.content, isStreaming: false }
                : m
            )
          );
          break;

        case "agent.event": {
          const eventLog: AgentEvent = {
            id: uuidv4(),
            eventName: data.event_name,
            data: data.data,
            timestamp: Date.now(),
          };
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantMsgId
                ? { ...m, agentEvents: [...(m.agentEvents ?? []), eventLog] }
                : m
            )
          );
          break;
        }

        case "tool.execution_start": {
          const toolId = data.tool_call_id ?? uuidv4();
          const te: ToolExecution = {
            id: toolId,
            toolName: data.tool_name,
            args: data.args,
            status: "running",
            startedAt: Date.now(),
          };
          activeToolsById.set(toolId, te);
          const queue = activeToolIdsByName.get(data.tool_name) ?? [];
          queue.push(toolId);
          activeToolIdsByName.set(data.tool_name, queue);
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantMsgId
                ? { ...m, toolExecutions: [...(m.toolExecutions ?? []), te] }
                : m
            )
          );
          break;
        }

        case "tool.execution_complete": {
          let toolId = data.tool_call_id;

          if (!toolId) {
            const queue = activeToolIdsByName.get(data.tool_name) ?? [];
            toolId = queue.shift();
            activeToolIdsByName.set(data.tool_name, queue);
          }

          const te = toolId ? activeToolsById.get(toolId) : undefined;
          if (te) {
            const updated: ToolExecution = {
              ...te,
              result: data.result,
              status: "complete",
              completedAt: Date.now(),
            };
            activeToolsById.set(updated.id, updated);
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMsgId
                  ? {
                      ...m,
                      toolExecutions: (m.toolExecutions ?? []).map((t) =>
                        t.id === te.id ? updated : t
                      ),
                    }
                  : m
              )
            );
          } else {
            setMessages((prev) =>
              prev.map((m) => {
                if (m.id !== assistantMsgId) return m;

                const runningTools = (m.toolExecutions ?? []).filter(
                  (tool) => tool.status === "running"
                );
                const fallbackTarget = [...runningTools]
                  .reverse()
                  .find((tool) => tool.toolName === data.tool_name)
                  ?? [...runningTools].reverse()[0];

                if (fallbackTarget) {
                  return {
                    ...m,
                    toolExecutions: (m.toolExecutions ?? []).map((tool) =>
                      tool.id === fallbackTarget.id
                        ? {
                            ...tool,
                            status: "complete",
                            result: data.result,
                            completedAt: Date.now(),
                          }
                        : tool
                    ),
                  };
                }

                const orphanCompleted: ToolExecution = {
                  id: uuidv4(),
                  toolName: data.tool_name,
                  status: "complete",
                  startedAt: Date.now(),
                  completedAt: Date.now(),
                  result: data.result,
                };

                return {
                  ...m,
                  toolExecutions: [...(m.toolExecutions ?? []), orphanCompleted],
                };
              })
            );
          }
          break;
        }

        case "session.idle":
          finalizeRunningTools();
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantMsgId ? { ...m, isStreaming: false } : m
            )
          );
          setIsLoading(false);
          break;

        case "error":
          finalizeRunningTools("Tool execution interrupted");
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantMsgId
                ? {
                    ...m,
                    content: m.content || `❌ Error: ${data.message}`,
                    isStreaming: false,
                  }
                : m
            )
          );
          setIsLoading(false);
          break;
      }
    };

    wsRef.current.send(
      JSON.stringify({ prompt, model: selectedModel })
    );
  }, [inputValue, isLoading, selectedModel]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const handleNewConversation = async () => {
    if (sessionId) {
      wsRef.current?.close();
      deleteSession(sessionId);
    }
    setMessages([]);
    setApprovalReport(null);
    setReportStreaming(false);
    setIsLoading(false);
    await initSession();
  };

  const handleMunicipalityTrigger = () => {
    const freeText = inputValue.trim();
    if (freeText) {
      setInputValue("");
      sendMessage(freeText);
    } else {
      sendMessage(MUNICIPALITY_TRIGGER_PROMPT);
    }
  };

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  return (
    <div className="flex flex-col h-screen bg-gray-50 dark:bg-gray-950">
      {/* Header */}
      <header className="flex items-center justify-between px-4 py-3
        bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800 shadow-sm shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-green-600 flex items-center justify-center text-white text-lg">
            🗼
          </div>
          <div>
            <h1 className="text-sm font-semibold text-gray-900 dark:text-gray-100">
              Site Approval Bot
            </h1>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              Powered by GitHub Copilot SDK · WorkIQ（M365 Copilot）
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <ModelSelector
            models={models}
            selected={selectedModel}
            onChange={setSelectedModel}
            disabled={isLoading}
          />
          <button
            onClick={handleNewConversation}
            disabled={isLoading}
            className="text-xs px-3 py-1.5 rounded-lg border border-gray-300 dark:border-gray-600
              hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-600 dark:text-gray-400
              disabled:opacity-50 transition-colors"
          >
            + New chat
          </button>
        </div>
      </header>

      {/* Municipality trigger banner */}
      <div className="shrink-0 px-4 py-2 bg-amber-50 dark:bg-amber-950/40
        border-b border-amber-200 dark:border-amber-800 flex items-center gap-3">
        <span className="text-sm text-amber-700 dark:text-amber-300 font-medium">
          📬 A市から設置許可メールが到着
        </span>
        <button
          onClick={handleMunicipalityTrigger}
          disabled={isLoading}
          className="text-xs px-3 py-1 rounded-lg bg-amber-500 hover:bg-amber-600 text-white
            disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-medium shrink-0"
        >
          {inputValue.trim() ? "送信" : "承認フローを開始"}
        </button>
        {!inputValue.trim() && (
          <span className="text-xs text-amber-600 dark:text-amber-400">
            ※ 下のテキストフィールドに入力すると、その内容が送信されます
          </span>
        )}
      </div>

      {/* 2-pane main area */}
      <div className="flex flex-1 min-h-0">
        {/* Left pane — Chat */}
        <div className="flex flex-col flex-1 min-w-0 border-r border-gray-200 dark:border-gray-800">
          {/* Message list */}
          <MessageList messages={messages} />

          {/* Input area */}
          <div className="shrink-0 bg-white dark:bg-gray-900 border-t border-gray-200 dark:border-gray-800 px-4 py-3">
            <div className="flex gap-2 items-end">
              <textarea
                ref={inputRef}
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={isLoading}
                placeholder="メッセージを入力… (Enter で送信、Shift+Enter で改行)"
                rows={1}
                className="flex-1 resize-none rounded-xl border border-gray-300 dark:border-gray-600
                  bg-gray-50 dark:bg-gray-800 text-gray-900 dark:text-gray-100
                  px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-green-500
                  disabled:opacity-50 placeholder-gray-400 dark:placeholder-gray-500
                  max-h-40 overflow-y-auto"
                style={{ minHeight: "48px" }}
                onInput={(e) => {
                  const el = e.currentTarget;
                  el.style.height = "auto";
                  el.style.height = Math.min(el.scrollHeight, 160) + "px";
                }}
              />
              <button
                onClick={() => sendMessage()}
                disabled={isLoading || !inputValue.trim()}
                className="px-4 py-3 rounded-xl bg-green-600 hover:bg-green-700 text-white
                  disabled:opacity-50 disabled:cursor-not-allowed transition-colors shrink-0"
                aria-label="Send message"
              >
                {isLoading ? (
                  <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                ) : (
                  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                  </svg>
                )}
              </button>
            </div>
            <p className="text-xs text-gray-400 dark:text-gray-600 text-center mt-2">
              Session: {sessionId?.slice(0, 8) ?? "—"}
            </p>
          </div>
        </div>

        {/* Right pane — Approval Report */}
        <div className="w-[45%] shrink-0 flex flex-col min-h-0">
          <ApprovalReportPanel report={approvalReport} isStreaming={reportStreaming} />
        </div>
      </div>
    </div>
  );
}

