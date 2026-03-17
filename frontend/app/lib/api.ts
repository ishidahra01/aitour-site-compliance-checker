// API client for the support agent backend

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const WS_BASE = API_BASE.replace(/^http/, "ws");

export async function fetchModels(): Promise<{ id: string; name: string }[]> {
  try {
    const res = await fetch(`${API_BASE}/models`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    return data.models ?? [];
  } catch {
    return [
      { id: "gpt-4o", name: "GPT-4o" },
      { id: "gpt-4.1", name: "GPT-4.1" },
      { id: "claude-sonnet-4-5", name: "Claude Sonnet 4.5" },
      { id: "o4-mini", name: "o4-mini" },
    ];
  }
}

export async function createSession(): Promise<string> {
  const res = await fetch(`${API_BASE}/sessions`, { method: "POST" });
  if (!res.ok) throw new Error(`Failed to create session: HTTP ${res.status}`);
  const data = await res.json();
  return data.session_id;
}

export async function deleteSession(sessionId: string): Promise<void> {
  await fetch(`${API_BASE}/sessions/${sessionId}`, { method: "DELETE" });
}

export function connectWebSocket(sessionId: string): WebSocket {
  return new WebSocket(`${WS_BASE}/ws/chat/${sessionId}`);
}

export function getReportDownloadUrl(filename: string): string {
  return `${API_BASE}/reports/${encodeURIComponent(filename)}`;
}
