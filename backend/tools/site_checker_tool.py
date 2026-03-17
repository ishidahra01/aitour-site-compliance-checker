"""
Site Standards Checker Tool.

Rule-based compliance checker for mobile base station site installation.
Accepts structured data gathered by the agent from Work IQ MCP tools and
applies fixed criteria to produce a structured verdict.
"""
from __future__ import annotations

import json
import logging
from typing import List, Optional

from pydantic import BaseModel, Field
from copilot import define_tool

logger = logging.getLogger(__name__)


class SourceInput(BaseModel):
    type: str = Field(description="Source type: 'email', 'meeting', or 'document'")
    title: str = Field(description="Source title")
    date: str = Field(description="Source date, e.g. '5/12'")
    author: str = Field(description="Source author name")
    summary: Optional[str] = Field(
        default=None,
        description="Brief summary of the source content in Japanese",
    )
    url: Optional[str] = Field(
        default=None,
        description="URL or link to the source (e.g. Teams meeting link, email permalink, SharePoint URL)",
    )


class SiteStandardsCheckerParams(BaseModel):
    site_id: str = Field(description="Site identifier, e.g. 'Site-2024-0847'")
    site_name: str = Field(description="Site display name in Japanese")
    antenna_height_required_m: float = Field(
        description="Required antenna height in meters from RF design"
    )
    antenna_height_limit_m: float = Field(
        description="Municipal height limit in meters from ordinance"
    )
    current_coverage_pct: float = Field(
        description="Current coverage percentage (0-100) from RF simulation"
    )
    coverage_standard_pct: float = Field(
        description="Company coverage standard percentage (0-100)"
    )
    alternative_coverage_pct: Optional[float] = Field(
        default=None,
        description="Coverage percentage with the alternative solution",
    )
    alternative_name: Optional[str] = Field(
        default=None,
        description="Name of the alternative solution in Japanese, e.g. 'スモールセル×2'",
    )
    alternative_cost_delta: Optional[str] = Field(
        default=None,
        description="Cost impact description for the alternative solution",
    )
    alternative_timeline_delta: Optional[str] = Field(
        default=None,
        description="Timeline impact for the alternative solution, e.g. '+2週間'",
    )
    municipality_conditions_met: List[str] = Field(
        default_factory=list,
        description="List of municipality conditions that are satisfied (Japanese)",
    )
    municipality_conditions_pending: List[str] = Field(
        default_factory=list,
        description="List of municipality conditions still pending (Japanese)",
    )
    sources: List[SourceInput] = Field(
        default_factory=list,
        description="Data sources referenced when gathering information",
    )


@define_tool(
    description=(
        "Rule-based site standards checker for base station installation compliance. "
        "Applies fixed engineering criteria to structured data gathered from Work IQ "
        "to determine whether the site meets installation standards. "
        "Returns a structured JSON compliance report with verdict, checks, alternatives, "
        "recommended actions, and cited sources."
    )
)
async def site_standards_checker(params: SiteStandardsCheckerParams) -> str:
    """Apply rule-based compliance checks and return a structured JSON report."""
    checks = []

    # 1. Coverage standard check
    coverage_ok = params.current_coverage_pct >= params.coverage_standard_pct
    checks.append(
        {
            "item": "カバレッジ基準",
            "standard": f"{params.coverage_standard_pct:.0f}%",
            "current": f"{params.current_coverage_pct:.0f}%",
            "status": "pass" if coverage_ok else "fail",
        }
    )

    # 2. Antenna height vs. municipal ordinance
    height_ok = params.antenna_height_required_m <= params.antenna_height_limit_m
    checks.append(
        {
            "item": "アンテナ高さ（条例制限）",
            "standard": f"≤{params.antenna_height_limit_m:.0f}m",
            "current": f"{params.antenna_height_required_m:.0f}m",
            "status": "pass" if height_ok else "fail",
        }
    )

    # 3. Municipality conditions — met
    for cond in params.municipality_conditions_met:
        checks.append(
            {
                "item": cond,
                "standard": "充足",
                "current": "充足",
                "status": "pass",
            }
        )

    # 4. Municipality conditions — pending
    for cond in params.municipality_conditions_pending:
        checks.append(
            {
                "item": cond,
                "standard": "充足",
                "current": "保留",
                "status": "constraint",
            }
        )

    fail_count = sum(1 for c in checks if c["status"] == "fail")
    has_viable_alt = (
        params.alternative_coverage_pct is not None
        and params.alternative_coverage_pct >= params.coverage_standard_pct
    )

    # Verdict
    if fail_count == 0:
        verdict = "go"
        verdict_reason = "すべての設置基準を満たしており、設置可能です。"
    elif fail_count > 0 and has_viable_alt:
        verdict = "conditional_go"
        verdict_reason = (
            f"現状ではカバレッジ基準（{params.coverage_standard_pct:.0f}%）を"
            f"満たしません（現状 {params.current_coverage_pct:.0f}%）。"
            f"ただし代替案「{params.alternative_name}」を採用すると"
            f"カバレッジ {params.alternative_coverage_pct:.0f}% を達成でき、"
            "基準を満たすことが可能です。コスト・工期の追加承認が必要です。"
        )
    else:
        verdict = "no_go"
        verdict_reason = (
            "現状および代替案を含めても設置基準を満たすことができません。"
            "再設計が必要です。"
        )

    # Alternatives
    alternatives = []
    if params.alternative_name and params.alternative_coverage_pct is not None:
        alternatives.append(
            {
                "name": params.alternative_name,
                "coverage": f"{params.alternative_coverage_pct:.0f}%",
                "cost_delta": params.alternative_cost_delta or "要試算",
                "timeline_delta": params.alternative_timeline_delta or "要確認",
            }
        )

    # Recommended actions
    actions: list[str] = []
    if verdict == "conditional_go":
        cost_label = params.alternative_cost_delta or "要試算"
        actions.append(
            f"代替案「{params.alternative_name}」のコスト増額（{cost_label}）について上位承認を取得する"
        )
        if params.alternative_timeline_delta:
            actions.append(
                f"工期延長（{params.alternative_timeline_delta}）を考慮したプロジェクト計画を更新する"
            )
        actions.append("代替案の詳細設計・ベンダー選定を開始する")
    for cond in params.municipality_conditions_pending:
        actions.append(f"自治体条件「{cond}」の確認・対応を完了させる")
    if not actions:
        actions.append("設置工事の最終スケジュールを確定する")

    result = {
        "verdict": verdict,
        "verdict_reason": verdict_reason,
        "checks": checks,
        "alternatives": alternatives,
        "actions": actions,
        "sources": [
            s.model_dump() if hasattr(s, "model_dump") else dict(s)
            for s in params.sources
        ],
        "coverage": {
            "current": params.current_coverage_pct,
            "standard": params.coverage_standard_pct,
            "alternative": params.alternative_coverage_pct,
        },
    }

    logger.info(
        "site_standards_checker: verdict=%s site=%s", verdict, params.site_id
    )
    return json.dumps(result, ensure_ascii=False, indent=2)
