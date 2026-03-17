"""
Site Approval Bot — Copilot SDK orchestrator.

Manages the lifecycle of GitHub Copilot SDK sessions, attaches the optional
Work IQ MCP server, and registers the local PowerPoint generation tool.

An AI agent that collects past discussion context via Work IQ MCP and
generates structured site approval reports when municipality permission
emails arrive.
"""
from __future__ import annotations

import asyncio
import logging
import os
import json
from typing import Any, AsyncIterator, Dict, Optional

from copilot import CopilotClient, PermissionHandler

from tools import (
    generate_powerpoint_tool,
)
from skills import SKILLS_DIR

logger = logging.getLogger(__name__)

_SUPPRESSED_AGENT_EVENTS = {
    "assistant.message_delta",
    "assistant.message",
    "assistant.streaming_delta",
    "assistant.usage",
    "tool.execution_start",
    "tool.execution_complete",
    "session.idle",
    # Noisy / low-value events filtered from the UI
    "pending_messages.modified",
    "user.message",
    "assistant.turn_start",
    "session.usage_info",
    "assistant.reasoning_delta",
    "assistant.reasoning_summary_delta",
    "assistant.reasoning_summary",
    "conversation.message_added",
    "conversation.updated",
}


def _event_data_to_dict(data: Any) -> dict[str, Any]:
    """Best-effort conversion of Copilot SDK event payloads to dict."""
    if data is None:
        return {}
    if isinstance(data, dict):
        return data

    for method_name in ("model_dump", "dict", "to_dict"):
        method = getattr(data, method_name, None)
        if callable(method):
            try:
                dumped = method()
                if isinstance(dumped, dict):
                    return dumped
            except Exception:
                pass

    try:
        attrs = vars(data)
        if isinstance(attrs, dict) and attrs:
            return attrs
    except Exception:
        pass

    return {"value": str(data)}


def _format_tool_result(value: Any) -> str:
    """Normalize tool result payloads to displayable text."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if text:
                    parts.append(str(text))
                else:
                    parts.append(json.dumps(item, ensure_ascii=False, default=str))
            else:
                parts.append(str(item))
        return "\n\n".join(p for p in parts if p)
    if isinstance(value, dict):
        content = value.get("content")
        if content is not None:
            content_text = _format_tool_result(content)
            if content_text:
                return content_text
        return json.dumps(value, ensure_ascii=False, default=str, indent=2)
    return str(value)


def _extract_tool_result(data: Any, data_dict: dict[str, Any]) -> str:
    """Extract tool result from multiple possible SDK payload shapes."""
    candidates = [
        data_dict.get("result"),
        data_dict.get("tool_result"),
        data_dict.get("output"),
        data_dict.get("content"),
        data_dict.get("message"),
    ]
    for candidate in candidates:
        text = _format_tool_result(candidate)
        if text:
            return text

    fallback_attr = getattr(data, "result", None)
    fallback_text = _format_tool_result(fallback_attr)
    if fallback_text:
        return fallback_text

    return ""


def _build_byok_provider() -> Dict[str, Any]:
    """Build a BYOK provider config from environment variables."""
    provider_type = os.environ.get("BYOK_PROVIDER", "openai")
    base_url = os.environ.get("BYOK_BASE_URL", "")
    api_key = os.environ.get("BYOK_API_KEY", "")
    config: Dict[str, Any] = {
        "type": provider_type,
        "base_url": base_url,
    }
    if api_key:
        config["api_key"] = api_key
    if provider_type == "azure":
        config["azure"] = {
            "api_version": os.environ.get("BYOK_AZURE_API_VERSION", "2024-10-21")
        }
    return config


def _resolve_cli_path() -> str | None:
    """Resolve Copilot CLI path only when explicitly requested."""
    env_path = os.environ.get("COPILOT_CLI_PATH")
    if env_path:
        return env_path

    # If not set, let the SDK decide how to locate the CLI.
    return None


def _build_mcp_servers() -> Dict[str, Any]:
    """Build MCP server configuration for session-level MCP tools."""
    if os.environ.get("WORKIQ_ENABLED", "false").lower() != "true":
        return {}

    return {
        "workiq": {
            "type": "local",
            "command": "npx",
            "args": ["-y", "@microsoft/workiq", "--account", "hishida@MngEnvMCAP873995.onmicrosoft.com", "mcp"],
            "tools": ["*"],
        }
    }


def _build_client() -> CopilotClient:
    """Create a CopilotClient, supporting both GitHub auth and BYOK."""
    github_token = os.environ.get("COPILOT_GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    cli_path = _resolve_cli_path()

    # BYOK configuration (no GitHub subscription needed)
    byok_provider = os.environ.get("BYOK_PROVIDER")
    if byok_provider:
        logger.info("Using BYOK provider: %s", byok_provider)

    client_opts: Dict[str, Any] = {
        "log_level": os.environ.get("LOG_LEVEL", "warning"),
        "auto_restart": True,
    }
    if os.environ.get("WORKIQ_ENABLED", "false").lower() == "true":
        client_opts["cli_args"] = ["--allow-all-tools", "--allow-all-paths"]
    if cli_path:
        client_opts["cli_path"] = cli_path
    if github_token:
        client_opts["github_token"] = github_token

    return CopilotClient(client_opts)


class SupportAgent:
    """
    Wraps the GitHub Copilot SDK to provide the Site Approval Bot agent.

    One shared CopilotClient is created per application instance.
    Individual chat conversations each get their own CopilotSession.
    """

    def __init__(self) -> None:
        self._client: Optional[CopilotClient] = None
        self._sessions: Dict[str, Any] = {}
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        """Start the underlying Copilot CLI server."""
        self._client = _build_client()
        await self._client.start()
        logger.info("Copilot SDK client started.")

    async def stop(self) -> None:
        """Shut down all sessions and the CLI server."""
        for session in list(self._sessions.values()):
            try:
                await session.destroy()
            except Exception:
                pass
        self._sessions.clear()
        if self._client:
            await self._client.stop()
        logger.info("Copilot SDK client stopped.")

    async def list_models(self) -> list[dict]:
        """Return models available via the Copilot CLI."""
        if not self._client:
            return []
        try:
            models = await self._client.list_models()
            return [{"id": m.id, "name": getattr(m, "display_name", m.id)} for m in models]
        except Exception as exc:
            logger.warning("Could not list models: %s", exc)
            return [
                {"id": "gpt-4o", "name": "GPT-4o"},
                {"id": "gpt-4.1", "name": "GPT-4.1"},
                {"id": "claude-sonnet-4-5", "name": "Claude Sonnet 4.5"},
                {"id": "o4-mini", "name": "o4-mini"},
            ]

    async def get_or_create_session(self, session_id: str, model: str) -> Any:
        """Get an existing session or create a new one for the given ID."""
        async with self._lock:
            if session_id in self._sessions:
                return self._sessions[session_id]

            byok_provider = os.environ.get("BYOK_PROVIDER")
            session_config: Dict[str, Any] = {
                "session_id": session_id,
                "model": model,
                "streaming": True,
                "skill_directories": [SKILLS_DIR],
                "on_permission_request": PermissionHandler.approve_all,
                "tools": [generate_powerpoint_tool],
            }

            mcp_servers = _build_mcp_servers()
            if mcp_servers:
                session_config["mcp_servers"] = mcp_servers

            if byok_provider:
                session_config["provider"] = _build_byok_provider()

            session = await self._client.create_session(session_config)
            self._sessions[session_id] = session
            logger.info("Created session %s (model=%s)", session_id, model)
            return session

    async def send_message(
        self,
        session_id: str,
        prompt: str,
        model: str = "gpt-4o",
    ) -> AsyncIterator[dict]:
        """
        Send a message to a session and yield SSE-style event dicts.

        Yields dicts with shape:
          {"type": "assistant.message_delta", "content": "..."}
          {"type": "tool.execution_start", "tool_name": "...", "args": {...}}
          {"type": "tool.execution_complete", "tool_name": "...", "result": "..."}
          {"type": "assistant.message", "content": "..."}
          {"type": "session.idle"}
          {"type": "error", "message": "..."}
        """
        queue: asyncio.Queue[dict | None] = asyncio.Queue()

        async def _run() -> None:
            try:
                session = await self.get_or_create_session(session_id, model)
                done_event = asyncio.Event()

                def on_event(event: Any) -> None:
                    evt_type = event.type.value if hasattr(event.type, "value") else str(event.type)
                    data = event.data if hasattr(event, "data") else {}
                    data_dict = _event_data_to_dict(data)

                    if evt_type not in _SUPPRESSED_AGENT_EVENTS:
                        queue.put_nowait({
                            "type": "agent.event",
                            "event_name": evt_type,
                            "data": data_dict,
                        })

                    if evt_type == "assistant.message_delta":
                        queue.put_nowait({
                            "type": "assistant.message_delta",
                            "content": data_dict.get("delta_content") or getattr(data, "delta_content", "") or "",
                        })
                    elif evt_type == "assistant.message":
                        queue.put_nowait({
                            "type": "assistant.message",
                            "content": data_dict.get("content") or getattr(data, "content", "") or "",
                        })
                    elif evt_type == "tool.execution_start":
                        queue.put_nowait({
                            "type": "tool.execution_start",
                            "tool_name": data_dict.get("tool_name") or data_dict.get("name") or getattr(data, "tool_name", "unknown"),
                            "args": data_dict.get("tool_args") or data_dict.get("arguments") or getattr(data, "tool_args", {}) or {},
                            "tool_call_id": data_dict.get("tool_call_id") or data_dict.get("call_id") or data_dict.get("id"),
                        })
                    elif evt_type == "tool.execution_complete":
                        queue.put_nowait({
                            "type": "tool.execution_complete",
                            "tool_name": data_dict.get("tool_name") or data_dict.get("name") or getattr(data, "tool_name", "unknown"),
                            "result": _extract_tool_result(data, data_dict),
                            "tool_call_id": data_dict.get("tool_call_id") or data_dict.get("call_id") or data_dict.get("id"),
                        })
                    elif evt_type == "session.idle":
                        queue.put_nowait({"type": "session.idle"})
                        queue.put_nowait(None)  # sentinel
                        done_event.set()

                unsubscribe = session.on(on_event)
                try:
                    await session.send({"prompt": prompt})
                    # Wait up to 5 minutes for session.idle
                    await asyncio.wait_for(done_event.wait(), timeout=300)
                except asyncio.TimeoutError:
                    queue.put_nowait({"type": "error", "message": "Request timed out."})
                    queue.put_nowait(None)
                finally:
                    unsubscribe()

            except Exception as exc:
                logger.exception("Error in send_message")
                queue.put_nowait({"type": "error", "message": str(exc)})
                queue.put_nowait(None)

        asyncio.create_task(_run())

        while True:
            item = await queue.get()
            if item is None:
                break
            yield item

    async def delete_session(self, session_id: str) -> None:
        """Destroy and remove a session."""
        async with self._lock:
            session = self._sessions.pop(session_id, None)
        if session:
            await session.destroy()
            logger.info("Deleted session %s", session_id)
