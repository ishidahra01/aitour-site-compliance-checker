"use client";

import { useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ChatMessage } from "@/app/lib/types";
import AgentEventCard from "./AgentEventCard";
import ToolExecutionCard from "./ToolExecutionCard";

interface Props {
  messages: ChatMessage[];
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4`}>
      {/* Avatar */}
      {!isUser && (
        <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center
          text-white text-sm font-bold mr-2 mt-1 shrink-0">
          AI
        </div>
      )}

      <div className={`max-w-[80%] ${isUser ? "items-end" : "items-start"} flex flex-col`}>
        {/* Agent execution logs (Copilot SDK events) */}
        {!isUser && message.agentEvents && message.agentEvents.length > 0 && (
          <div className="w-full mb-2">
            {message.agentEvents.map((event) => (
              <AgentEventCard key={event.id} event={event} />
            ))}
          </div>
        )}

        {/* Tool executions (shown before the message for assistant) */}
        {!isUser && message.toolExecutions && message.toolExecutions.length > 0 && (
          <div className="w-full mb-2">
            {message.toolExecutions.map((te) => (
              <ToolExecutionCard key={te.id} execution={te} />
            ))}
          </div>
        )}

        {/* Message bubble */}
        {message.content && (
          <div
            className={`px-4 py-3 rounded-2xl text-sm leading-relaxed ${
              isUser
                ? "bg-blue-600 text-white rounded-tr-sm"
                : "bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 text-gray-900 dark:text-gray-100 rounded-tl-sm shadow-sm"
            } ${message.isStreaming ? "animate-pulse" : ""}`}
          >
            {isUser ? (
              <span className="whitespace-pre-wrap">{message.content}</span>
            ) : (
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  code: ({ node, className, children, ...props }: any) => {
                    const isInline = !className;
                    return isInline ? (
                      <code className="bg-gray-100 dark:bg-gray-700 px-1 py-0.5 rounded text-xs" {...props}>
                        {children}
                      </code>
                    ) : (
                      <pre className="bg-gray-100 dark:bg-gray-800 rounded-lg p-3 overflow-auto mt-2 mb-2">
                        <code className="text-xs" {...props}>{children}</code>
                      </pre>
                    );
                  },
                  a: ({ href, children }) => (
                    <a href={href} target="_blank" rel="noopener noreferrer"
                      className="text-blue-500 hover:text-blue-600 underline">
                      {children}
                    </a>
                  ),
                  h2: ({ children }) => (
                    <h2 className="text-base font-bold mt-3 mb-1">{children}</h2>
                  ),
                  h3: ({ children }) => (
                    <h3 className="text-sm font-semibold mt-2 mb-1">{children}</h3>
                  ),
                  ul: ({ children }) => (
                    <ul className="list-disc list-inside my-1 space-y-0.5">{children}</ul>
                  ),
                  ol: ({ children }) => (
                    <ol className="list-decimal list-inside my-1 space-y-0.5">{children}</ol>
                  ),
                  hr: () => <hr className="border-gray-200 dark:border-gray-600 my-3" />,
                  blockquote: ({ children }) => (
                    <blockquote className="border-l-4 border-blue-400 pl-3 italic text-gray-600 dark:text-gray-400 my-2">
                      {children}
                    </blockquote>
                  ),
                }}
              >
                {message.content}
              </ReactMarkdown>
            )}
          </div>
        )}

        {/* Timestamp */}
        <span className="text-xs text-gray-400 mt-1 px-1">
          {new Date(message.timestamp).toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </span>
      </div>

      {isUser && (
        <div className="w-8 h-8 rounded-full bg-gray-300 dark:bg-gray-600 flex items-center justify-center
          text-gray-700 dark:text-gray-200 text-sm font-bold ml-2 mt-1 shrink-0">
          👤
        </div>
      )}
    </div>
  );
}

function TypingIndicator() {
  return (
    <div className="flex justify-start mb-4">
      <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center
        text-white text-sm font-bold mr-2 shrink-0">
        AI
      </div>
      <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700
        rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm">
        <div className="flex gap-1 items-center h-4">
          {[0, 1, 2].map((i) => (
            <span
              key={i}
              className="w-2 h-2 rounded-full bg-gray-400 animate-bounce"
              style={{ animationDelay: `${i * 0.15}s` }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

export default function MessageList({ messages }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const isLoading = messages.some((m) => m.isStreaming);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (messages.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-center p-8">
        <div className="text-5xl mb-4">🗼</div>
        <h2 className="text-xl font-semibold text-gray-700 dark:text-gray-300 mb-2">
          Site Approval Bot
        </h2>
        <p className="text-gray-500 dark:text-gray-400 max-w-md text-sm leading-relaxed">
          自治体からの設置許可メールをトリガーに、過去の全議論を自動で収集し
          承認レポートを生成します。
        </p>
        <div className="mt-6 flex flex-wrap gap-2 justify-center">
          {[
            "A市 公園用地の設置条件を教えて",
            "鈴木さんの設計制約を確認して",
            "スモールセルのコスト承認状況は？",
          ].map((hint) => (
            <span
              key={hint}
              className="px-3 py-1.5 bg-green-50 dark:bg-green-900/30 text-green-700 dark:text-green-300
                rounded-full text-xs border border-green-200 dark:border-green-700"
            >
              {hint}
            </span>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto px-4 py-4">
      {messages.map((msg) => (
        <MessageBubble key={msg.id} message={msg} />
      ))}
      {isLoading && <TypingIndicator />}
      <div ref={bottomRef} />
    </div>
  );
}
