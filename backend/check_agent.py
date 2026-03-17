"""
Check Agent for the 基地局設置チェッカー demo.

Manages compliance-check jobs: creates a Copilot SDK session per job,
attaches the Work IQ MCP server and the site_standards_checker tool,
streams execution log events through an asyncio.Queue, and captures the
final CheckResult JSON emitted by the site_standards_checker tool.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from copilot import CopilotClient, PermissionHandler

from tools.site_checker_tool import site_standards_checker
from skills.site_checker import SITE_CHECKER_SKILLS_DIR

logger = logging.getLogger(__name__)

# Sites available in the demo UI
SITES: Dict[str, str] = {
    "Site-2024-0847": "A市中央公園",
    "Site-2024-1023": "B市駅前広場",
    "Site-2024-1156": "C市海浜公園",
}


# ---------------------------------------------------------------------------
# Helpers (mirror agent.py to avoid circular imports)
# ---------------------------------------------------------------------------

def _event_data_to_dict(data: Any) -> Dict[str, Any]:
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


def _extract_result_str(data: Any, data_dict: Dict[str, Any]) -> str:
    for key in ("result", "tool_result", "output", "content", "message"):
        val = data_dict.get(key)
        if val is not None:
            if isinstance(val, str):
                return val
            try:
                return json.dumps(val, ensure_ascii=False)
            except Exception:
                return str(val)
    fallback = getattr(data, "result", None)
    if fallback is not None:
        return str(fallback)
    return ""


def _build_mcp_servers() -> Dict[str, Any]:
    if os.environ.get("WORKIQ_ENABLED", "false").lower() != "true":
        return {}
    return {
        "workiq": {
            "type": "local",
            "command": "npx",
            "args": ["-y", "@microsoft/workiq@latest", "mcp"],
            "tools": ["*"],
        }
    }


def _build_byok_provider() -> Dict[str, Any]:
    provider_type = os.environ.get("BYOK_PROVIDER", "openai")
    base_url = os.environ.get("BYOK_BASE_URL", "")
    api_key = os.environ.get("BYOK_API_KEY", "")
    config: Dict[str, Any] = {"type": provider_type, "base_url": base_url}
    if api_key:
        config["api_key"] = api_key
    if provider_type == "azure":
        config["azure"] = {
            "api_version": os.environ.get("BYOK_AZURE_API_VERSION", "2024-10-21")
        }
    return config


def _build_client() -> CopilotClient:
    github_token = os.environ.get("COPILOT_GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    cli_path = os.environ.get("COPILOT_CLI_PATH")

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


def _build_check_prompt(site_id: str, check_items: List[str]) -> str:
    site_name = SITES.get(site_id, site_id)
    items_str = "、".join(check_items) if check_items else "すべての項目"
    return (
        f"サイト「{site_name}（{site_id}）」の適合性チェックを実行してください。\n"
        f"チェック項目: {items_str}\n\n"
        "Work IQ MCP ツールを使って以下の情報を収集してから "
        "site_standards_checker ツールを呼び出してください：\n"
        "1. 自治体条件（高さ制限、外装規定、住民説明会等）\n"
        "2. RF 設計制約（必要アンテナ高、カバレッジシミュレーション）\n"
        "3. 設置基準書（カバレッジ基準値）\n"
        "4. 代替案の情報（スモールセル等）\n\n"
        "site_standards_checker ツールの戻り値 JSON のみを最終回答として出力してください。"
    )


# ---------------------------------------------------------------------------
# Job dataclass
# ---------------------------------------------------------------------------

@dataclass
class CheckJob:
    check_id: str
    site_id: str
    check_items: List[str]
    free_text: Optional[str]
    log_queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    result: Optional[Dict[str, Any]] = None
    done_event: asyncio.Event = field(default_factory=asyncio.Event)


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class CheckAgent:
    """
    Manages Copilot SDK sessions for site compliance check jobs.

    One CopilotClient is shared across all jobs.  Each job gets its own
    Copilot session identified by the job's check_id.
    """

    def __init__(self) -> None:
        self._client: Optional[CopilotClient] = None
        self._jobs: Dict[str, CheckJob] = {}

    async def start(self) -> None:
        self._client = _build_client()
        await self._client.start()
        logger.info("CheckAgent client started.")

    async def stop(self) -> None:
        if self._client:
            await self._client.stop()

    def create_job(
        self,
        site_id: str,
        check_items: List[str],
        free_text: Optional[str] = None,
    ) -> CheckJob:
        job = CheckJob(
            check_id=str(uuid.uuid4()),
            site_id=site_id,
            check_items=check_items,
            free_text=free_text,
        )
        self._jobs[job.check_id] = job
        asyncio.create_task(self._run_job(job))
        return job

    def get_job(self, check_id: str) -> Optional[CheckJob]:
        return self._jobs.get(check_id)

    # ------------------------------------------------------------------
    # Internal job runner
    # ------------------------------------------------------------------

    async def _run_job(self, job: CheckJob) -> None:
        try:
            await job.log_queue.put(
                {"type": "log", "message": "Copilot SDK セッションを開始しています..."}
            )

            byok_provider = os.environ.get("BYOK_PROVIDER")
            model = os.environ.get("BYOK_MODEL", "gpt-4o")

            session_config: Dict[str, Any] = {
                "session_id": job.check_id,
                "model": model,
                "streaming": False,
                "skill_directories": [SITE_CHECKER_SKILLS_DIR],
                "on_permission_request": PermissionHandler.approve_all,
                "tools": [site_standards_checker],
            }

            mcp_servers = _build_mcp_servers()
            if mcp_servers:
                session_config["mcp_servers"] = mcp_servers
                await job.log_queue.put(
                    {"type": "log", "message": "MCP: Work IQ サーバーに接続中..."}
                )

            if byok_provider:
                session_config["provider"] = _build_byok_provider()

            session = await self._client.create_session(session_config)

            await job.log_queue.put(
                {"type": "log", "message": f"Copilot SDK セッション開始 (model: {model})"}
            )
            if mcp_servers:
                await job.log_queue.put(
                    {"type": "log", "message": "MCP: Work IQ connected ✓"}
                )

            prompt = job.free_text or _build_check_prompt(job.site_id, job.check_items)
            done_event = asyncio.Event()
            result_container: Dict[str, Any] = {}

            def on_event(event: Any) -> None:
                evt_type = (
                    event.type.value
                    if hasattr(event.type, "value")
                    else str(event.type)
                )
                data = event.data if hasattr(event, "data") else {}
                data_dict = _event_data_to_dict(data)

                if evt_type == "tool.execution_start":
                    tool_name = (
                        data_dict.get("tool_name")
                        or data_dict.get("name")
                        or getattr(data, "tool_name", "unknown")
                    )
                    args = (
                        data_dict.get("tool_args")
                        or data_dict.get("arguments")
                        or getattr(data, "tool_args", {})
                        or {}
                    )

                    if tool_name == "site_standards_checker":
                        job.log_queue.put_nowait(
                            {
                                "type": "log",
                                "message": "site-standards-checker ツールを実行中...",
                            }
                        )
                    else:
                        query = args.get("query", "") if isinstance(args, dict) else ""
                        if query:
                            job.log_queue.put_nowait(
                                {
                                    "type": "log",
                                    "message": f'Work IQ クエリ: "{query}"',
                                }
                            )
                        else:
                            job.log_queue.put_nowait(
                                {"type": "log", "message": f"ツール実行: {tool_name}"}
                            )

                elif evt_type == "tool.execution_complete":
                    tool_name = (
                        data_dict.get("tool_name")
                        or data_dict.get("name")
                        or getattr(data, "tool_name", "unknown")
                    )
                    result_str = _extract_result_str(data, data_dict)

                    if tool_name == "site_standards_checker":
                        job.log_queue.put_nowait(
                            {"type": "log", "message": "レポート生成完了 ✓"}
                        )
                        try:
                            parsed = json.loads(result_str)
                            result_container["data"] = parsed
                        except Exception:
                            logger.warning(
                                "Could not parse site_standards_checker result: %r",
                                result_str[:200],
                            )
                    else:
                        # WorkIQ or other tool — emit a generic found message
                        job.log_queue.put_nowait(
                            {"type": "log", "message": "  → データ取得完了"}
                        )

                elif evt_type == "session.idle":
                    done_event.set()

            unsubscribe = session.on(on_event)
            try:
                await session.send({"prompt": prompt})
                await asyncio.wait_for(done_event.wait(), timeout=300)
            except asyncio.TimeoutError:
                await job.log_queue.put(
                    {"type": "error", "message": "タイムアウト（300秒）"}
                )
            finally:
                unsubscribe()

            if result_container.get("data"):
                job.result = result_container["data"]
                await job.log_queue.put(
                    {"type": "result", "data": job.result}
                )
            else:
                await job.log_queue.put(
                    {
                        "type": "error",
                        "message": "適合性チェック結果の取得に失敗しました。エージェントが site_standards_checker を呼び出さなかった可能性があります。",
                    }
                )

        except Exception as exc:
            logger.exception("CheckAgent job error: check_id=%s", job.check_id)
            await job.log_queue.put({"type": "error", "message": str(exc)})
        finally:
            await job.log_queue.put(None)  # sentinel — signals end of stream
            job.done_event.set()
