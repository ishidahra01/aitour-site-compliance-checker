"""
checker.py

Copilot SDK session manager for the base station compliance checker.
When GITHUB_TOKEN is set and the copilot package is installed, uses the real SDK.
Otherwise falls back to mock mode for demo purposes.
"""

from __future__ import annotations

import asyncio
import json
import os
import pathlib
import time
from typing import Any, Callable

from demo_data import MOCK_M365_DATA, SITES
from site_standards_checker import run_site_standards_checker

# Check whether the Copilot SDK is available
try:
    from copilot import CopilotClient, define_tool
    from copilot.types import PermissionRequestResult
    from pydantic import BaseModel, Field

    COPILOT_SDK_AVAILABLE = True
except ImportError:
    COPILOT_SDK_AVAILABLE = False

SKILLS_DIR = str(pathlib.Path(__file__).parent.parent / "skills")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")


async def run_copilot_check(
    site_id: str,
    check_items: list[str],
    emit: Callable[[dict], None],
) -> dict[str, Any]:
    """
    Run a compliance check using the real Copilot SDK with Work IQ MCP.
    """
    site = next((s for s in SITES if s["id"] == site_id), None)
    if site is None:
        raise ValueError(f"Unknown site: {site_id}")

    site_name = site["name"]

    from pydantic import BaseModel, Field  # noqa: F811

    # ─── Define the site-standards-checker tool ───────────────────────────
    class SiteDataParams(BaseModel):
        site_id: str = Field(description="Site identifier")
        emails_json: str = Field(
            description="JSON string of email data extracted from Work IQ"
        )
        meetings_json: str = Field(
            description="JSON string of meeting data extracted from Work IQ"
        )
        documents_json: str = Field(
            description="JSON string of document data extracted from Work IQ"
        )

    @define_tool(
        name="site_standards_checker",
        description=(
            "Rule-based compliance checker for base station site installation. "
            "Pass extracted M365 data to perform deterministic standards analysis."
        ),
        skip_permission=True,
    )
    async def site_standards_checker_tool(params: SiteDataParams) -> str:
        emit({"type": "log", "text": "Running site-standards-checker tool..."})
        site_data = {
            "emails": json.loads(params.emails_json),
            "meetings": json.loads(params.meetings_json),
            "documents": json.loads(params.documents_json),
        }
        result = run_site_standards_checker(site_data)
        for check in result.get("checks", []):
            status_icon = {"pass": "✓", "fail": "✗", "constraint": "△"}.get(
                check["status"], "?"
            )
            emit({
                "type": "log",
                "text": f"  → {check['item']}: {check['current']} vs 基準{check['standard']}: "
                        f"{status_icon}",
            })
        if result.get("alternatives"):
            alt = result["alternatives"][0]
            emit({"type": "log", "text": f"  → 代替案: {alt['name']} → {alt['coverage']}"})
        emit({"type": "log", "text": "Report generated ✓"})
        return json.dumps(result, ensure_ascii=False)

    # ─── Build prompt ─────────────────────────────────────────────────────
    check_labels = {
        "municipality": "自治体条件突合",
        "design_standards": "設計基準チェック",
        "alternatives": "代替案分析",
        "cost": "コスト試算",
    }
    selected = [check_labels.get(c, c) for c in check_items]
    prompt = (
        f"サイト「{site_name}」の適合性チェックを実行してください。\n"
        f"チェック項目: {', '.join(selected)}\n\n"
        "手順:\n"
        "1. Work IQ MCP を使用してM365から関連データを収集する\n"
        "   - 自治体条件メール（高さ制限、外装基準、住民説明会状況）\n"
        "   - RF設計技術制約メール（アンテナ高、カバレッジ試算）\n"
        "   - 設計会議議事録\n"
        "   - 設置基準書\n"
        "2. 収集したデータを site_standards_checker ツールに渡して適合性分析を実行する\n"
        "3. 分析結果のJSONをそのまま返す（追加説明不要）\n"
    )

    # ─── Start Copilot SDK session ────────────────────────────────────────
    emit({"type": "log", "text": "Copilot SDK session started (model: gpt-5)"})

    client = CopilotClient(
        config=None,
        auto_start=True,
    )
    if GITHUB_TOKEN:
        from copilot import SubprocessConfig  # type: ignore[attr-defined]
        client = CopilotClient(
            config=SubprocessConfig(github_token=GITHUB_TOKEN),
            auto_start=True,
        )

    await client.start()

    emit({"type": "log", "text": "MCP: connecting to workiq server..."})

    session = await client.create_session({
        "model": "gpt-5",
        "tools": [site_standards_checker_tool],
        "skill_directories": [SKILLS_DIR],
        "mcp_servers": {
            "workiq": {
                "type": "local",
                "command": "npx",
                "args": ["-y", "@microsoft/workiq@latest", "mcp"],
                "tools": ["*"],
            }
        },
        "on_permission_request": lambda req, inv: PermissionRequestResult(
            kind="approved"
        ),
    })

    emit({"type": "log", "text": "MCP: workiq connected ✓"})

    # ─── Capture events ───────────────────────────────────────────────────
    result_json: str | None = None
    done_event = asyncio.Event()

    def on_event(event):
        nonlocal result_json
        etype = getattr(event.type, "value", str(event.type))
        if etype == "assistant.message":
            content = getattr(event.data, "content", "")
            if content:
                # Try to parse as JSON result
                try:
                    parsed = json.loads(content)
                    if "verdict" in parsed:
                        result_json = content
                except (json.JSONDecodeError, AttributeError):
                    pass
        elif etype == "session.idle":
            done_event.set()
        elif etype == "tool.call":
            tool_name = getattr(event.data, "name", "")
            if tool_name and "workiq" in tool_name.lower():
                args = getattr(event.data, "arguments", {})
                query = args.get("query", "") if isinstance(args, dict) else ""
                if query:
                    emit({"type": "log", "text": f'Work IQ query: "{query}"'})

    session.on(on_event)

    await session.send(prompt)
    await asyncio.wait_for(done_event.wait(), timeout=120.0)

    await session.disconnect()
    await client.stop()

    if result_json:
        return json.loads(result_json)
    raise RuntimeError("No result returned from Copilot SDK session")


async def run_mock_check(
    site_id: str,
    check_items: list[str],
    emit: Callable[[dict], None],
) -> dict[str, Any]:
    """
    Mock compliance check that simulates Copilot SDK + Work IQ behavior.
    Used when SDK is unavailable or GITHUB_TOKEN is not set.
    """
    site = next((s for s in SITES if s["id"] == site_id), None)
    if site is None:
        raise ValueError(f"Unknown site: {site_id}")

    site_name_short = site["name"].split(" ")[0]

    async def log(text: str, delay: float = 0.4):
        await asyncio.sleep(delay)
        emit({"type": "log", "text": text})

    await log("Copilot SDK session started (model: gpt-5)", 0.3)
    await log("MCP: connecting to workiq server...", 0.6)
    await log("MCP: workiq connected ✓", 0.5)

    # Only run queries for the selected check items
    if "municipality" in check_items:
        await log(f'Work IQ query: "{site_name_short} 自治体条件"', 0.7)
        await log("  → Outlook: 中村メール (5/12) found", 0.4)
        await log("  → Teams: 設計会議議事録 (5/18) found", 0.4)

    if "design_standards" in check_items:
        await log(f'Work IQ query: "{site_name_short} RF設計 技術制約"', 0.7)
        await log("  → Outlook: 鈴木メール (5/15) found", 0.4)
        await log("  → SharePoint: 設置基準書 v3.2 found", 0.4)

    if "alternatives" in check_items:
        await log(f'Work IQ query: "{site_name_short} 代替案"', 0.6)
        await log("  → Outlook: 鈴木メール (5/15) found", 0.3)

    if "cost" in check_items:
        await log(f'Work IQ query: "{site_name_short} コスト試算"', 0.6)
        await log("  → Outlook: 鈴木メール (5/15) found", 0.3)

    await log("Running site-standards-checker tool...", 0.8)

    # Use real rule-based checker with mock M365 data
    mock_data = MOCK_M365_DATA.get(site_id, {"emails": [], "meetings": [], "documents": []})
    result = run_site_standards_checker(mock_data)

    for check in result.get("checks", []):
        status_icon = {"pass": "✓", "fail": "✗", "constraint": "△"}.get(
            check["status"], "?"
        )
        await log(
            f"  → {check['item']}: {check['current']} vs 基準{check['standard']}: {status_icon}",
            0.35,
        )

    if result.get("alternatives"):
        alt = result["alternatives"][0]
        await log(f"  → 代替案: {alt['name']} → {alt['coverage']}", 0.4)

    await log("Report generated ✓", 0.5)

    return result


async def run_check(
    site_id: str,
    check_items: list[str],
    emit: Callable[[dict], None],
) -> dict[str, Any]:
    """
    Run compliance check, choosing real SDK or mock based on environment.
    """
    use_real_sdk = COPILOT_SDK_AVAILABLE and bool(GITHUB_TOKEN)

    if use_real_sdk:
        return await run_copilot_check(site_id, check_items, emit)
    else:
        return await run_mock_check(site_id, check_items, emit)
