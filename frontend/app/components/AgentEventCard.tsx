"use client";

import { useState } from "react";
import { AgentEvent } from "@/app/lib/types";

interface Props {
  event: AgentEvent;
}

function GitHubCopilotBadge() {
  return (
    <span className="flex items-center gap-1 shrink-0 text-xs font-semibold text-purple-700 dark:text-purple-300 bg-purple-100 dark:bg-purple-900/40 border border-purple-200 dark:border-purple-700 px-1.5 py-0.5 rounded-full">
      <svg viewBox="0 0 16 16" className="w-3 h-3" fill="currentColor" aria-hidden="true">
        <path d="M4 3h8v9H4V3zm8-1H4C3.45 2 3 2.45 3 3v9c0 .55.45 1 1 1h3.5l1 1.5h-.75a.25.25 0 0 0 0 .5h2.5a.25.25 0 0 0 0-.5h-.75l1-1.5H12c.55 0 1-.45 1-1V3c0-.55-.45-1-1-1zm-2 4.5a1 1 0 1 1-2.001.001A1 1 0 0 1 10 6.5zm-4 0a1 1 0 1 1-2.001.001A1 1 0 0 1 6 6.5z"/>
      </svg>
      GitHub Copilot
    </span>
  );
}

export default function AgentEventCard({ event }: Props) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="my-2 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden text-sm">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-3 py-2
          bg-gray-50 dark:bg-gray-800/60 hover:bg-gray-100 dark:hover:bg-gray-700/60
          transition-colors text-left"
      >
        <div className="flex items-center gap-2 min-w-0">
          <GitHubCopilotBadge />
          <span className="font-medium text-gray-700 dark:text-gray-300 truncate">
            {event.eventName}
          </span>
          <span className="text-xs text-gray-400 shrink-0">
            {new Date(event.timestamp).toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
              second: "2-digit",
            })}
          </span>
        </div>
        <span className="text-gray-400 text-xs">{expanded ? "▲ hide" : "▼ show"}</span>
      </button>

      {expanded && (
        <div className="px-3 py-2 bg-white dark:bg-gray-900/40">
          <pre className="text-xs bg-gray-100 dark:bg-gray-800 rounded p-2 overflow-auto whitespace-pre-wrap break-words max-h-56">
            {JSON.stringify(event.data ?? {}, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
