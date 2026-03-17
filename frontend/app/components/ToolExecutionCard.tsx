"use client";

import { useState } from "react";
import { ToolExecution } from "@/app/lib/types";

function getToolIcon(toolName: string): string {
  if (toolName === "generate_powerpoint_tool") {
    return "📊";
  }
  if (toolName.toLowerCase().includes("workiq")) {
    return "🤖";
  }
  return "🔧";
}

function getToolLabel(toolName: string): string {
  if (toolName === "generate_powerpoint_tool") {
    return "PowerPoint Generator";
  }
  if (toolName.toLowerCase().includes("workiq")) {
    return `WorkIQ（M365 Copilot）: ${toolName}`;
  }
  return toolName;
}

interface Props {
  execution: ToolExecution;
}

export default function ToolExecutionCard({ execution }: Props) {
  const [expanded, setExpanded] = useState(false);
  const icon = getToolIcon(execution.toolName);
  const label = getToolLabel(execution.toolName);

  const isRunning = execution.status === "running";
  const duration =
    execution.completedAt && execution.startedAt
      ? ((execution.completedAt - execution.startedAt) / 1000).toFixed(1)
      : null;

  // Check if result contains a PowerPoint download link
  const pptxMatch = execution.result?.match(/GET \/reports\/(\S+\.pptx)/);

  return (
    <div className="my-2 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden text-sm">
      {/* Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-3 py-2
          bg-gray-50 dark:bg-gray-800/60 hover:bg-gray-100 dark:hover:bg-gray-700/60
          transition-colors text-left"
      >
        <div className="flex items-center gap-2">
          <span>{icon}</span>
          <span className="font-medium text-gray-700 dark:text-gray-300">{label}</span>
          {isRunning && (
            <span className="flex items-center gap-1 text-blue-500 text-xs animate-pulse">
              <span className="w-1.5 h-1.5 rounded-full bg-blue-500 inline-block" />
              Running…
            </span>
          )}
          {!isRunning && duration && (
            <span className="text-xs text-gray-400">{duration}s</span>
          )}
        </div>
        <span className="text-gray-400 text-xs">{expanded ? "▲ hide" : "▼ show"}</span>
      </button>

      {/* Body */}
      {expanded && (
        <div className="px-3 py-2 space-y-2 bg-white dark:bg-gray-900/40">
          {execution.args && Object.keys(execution.args).length > 0 && (
            <div>
              <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 mb-1">
                Arguments
              </p>
              <pre className="text-xs bg-gray-100 dark:bg-gray-800 rounded p-2 overflow-auto whitespace-pre-wrap break-words">
                {JSON.stringify(execution.args, null, 2)}
              </pre>
            </div>
          )}

          {execution.result && (
            <div>
              <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 mb-1">
                Result
              </p>
              <div className="text-xs bg-gray-100 dark:bg-gray-800 rounded p-2 overflow-auto max-h-48 whitespace-pre-wrap break-words">
                {execution.result}
              </div>
              {pptxMatch && (
                <a
                  href={`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/reports/${pptxMatch[1]}`}
                  download
                  className="mt-2 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg
                    bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium transition-colors"
                >
                  📥 Download PowerPoint
                </a>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
