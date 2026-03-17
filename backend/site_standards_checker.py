"""
site_standards_checker.py

Rule-based (non-LLM) compliance checker for base station site installation.
This is registered as a custom tool in the Copilot SDK session.
"""

from __future__ import annotations

from typing import Any


def run_site_standards_checker(site_data: dict[str, Any]) -> dict[str, Any]:
    """
    Perform rule-based compliance analysis on site data gathered from M365.

    Parameters:
        site_data: dict containing extracted data from emails, meetings, and documents

    Returns:
        CheckResult dict matching the defined JSON schema
    """
    emails = site_data.get("emails", [])
    meetings = site_data.get("meetings", [])
    documents = site_data.get("documents", [])

    # ─── Extract key values ─────────────────────────────────────────────────
    height_limit_m: int | None = None
    required_height_m: int | None = None
    coverage_current_pct: int | None = None
    coverage_standard_pct: int = 95
    resident_meeting_done: bool = False
    appearance_specified: bool = False
    alternative_coverage_pct: int | None = None
    alternative_cost_delta: str = "未算出"
    alternative_timeline_delta: str = "未算出"
    alternative_small_cells: int | None = None

    for email in emails:
        extracted = email.get("extracted", {})
        if "height_limit_m" in extracted:
            height_limit_m = extracted["height_limit_m"]
        if "required_antenna_height_m" in extracted:
            required_height_m = extracted["required_antenna_height_m"]
        if "coverage_at_15m_pct" in extracted:
            coverage_current_pct = extracted["coverage_at_15m_pct"]
        if "alternative_coverage_pct" in extracted:
            alternative_coverage_pct = extracted["alternative_coverage_pct"]
        if "alternative_cost_delta" in extracted:
            alternative_cost_delta = extracted["alternative_cost_delta"]
        if "alternative_timeline_delta" in extracted:
            alternative_timeline_delta = extracted["alternative_timeline_delta"]
        if "alternative_small_cells" in extracted:
            alternative_small_cells = extracted["alternative_small_cells"]
        if extracted.get("resident_meeting_done"):
            resident_meeting_done = True
        if extracted.get("appearance_color"):
            appearance_specified = True

    for doc in documents:
        extracted = doc.get("extracted", {})
        if "coverage_standard_pct" in extracted:
            coverage_standard_pct = extracted["coverage_standard_pct"]
        if extracted.get("resident_meeting_required") and not resident_meeting_done:
            resident_meeting_done = False

    # ─── Rule-based checks ──────────────────────────────────────────────────
    checks = []

    # Check 1: Coverage standard
    if coverage_current_pct is not None:
        coverage_meets = coverage_current_pct >= coverage_standard_pct
        checks.append({
            "item": "カバレッジ基準",
            "standard": f"≥{coverage_standard_pct}%",
            "current": f"{coverage_current_pct}%",
            "status": "fail" if not coverage_meets else "pass",
        })

    # Check 2: Height / municipality compliance
    if height_limit_m is not None and required_height_m is not None:
        height_ok = required_height_m <= height_limit_m
        checks.append({
            "item": "自治体高さ制限",
            "standard": f"≤{height_limit_m}m（景観条例）",
            "current": f"必要アンテナ高{required_height_m}m",
            "status": "constraint" if not height_ok else "pass",
        })

    # Check 3: Resident meeting
    checks.append({
        "item": "住民説明会",
        "standard": "設置前実施・同意書取得",
        "current": "実施済み・同意書取得済み" if resident_meeting_done else "未実施",
        "status": "pass" if resident_meeting_done else "fail",
    })

    # Check 4: Appearance standard
    checks.append({
        "item": "外装基準",
        "standard": "自治体指定色彩基準準拠",
        "current": "市指定色（アースブラウン/グレー）適用" if appearance_specified else "確認中",
        "status": "pass" if appearance_specified else "constraint",
    })

    # ─── Alternatives ───────────────────────────────────────────────────────
    alternatives = []
    if alternative_coverage_pct is not None and alternative_small_cells is not None:
        alternatives.append({
            "name": f"スモールセル×{alternative_small_cells}（高さ制限対応代替案）",
            "coverage": f"{alternative_coverage_pct}%",
            "cost_delta": alternative_cost_delta,
            "timeline_delta": alternative_timeline_delta,
        })

    # ─── Verdict logic ──────────────────────────────────────────────────────
    fail_count = sum(1 for c in checks if c["status"] == "fail")
    constraint_count = sum(1 for c in checks if c["status"] == "constraint")

    # If alternative resolves all fails/constraints → conditional_go
    alternative_resolves = (
        alternative_coverage_pct is not None
        and alternative_coverage_pct >= coverage_standard_pct
    )

    if fail_count == 0 and constraint_count == 0:
        verdict = "go"
        verdict_reason = "全項目が社内基準を満たしています。設置を推奨します。"
    elif alternative_resolves and fail_count <= 1 and constraint_count <= 1:
        verdict = "conditional_go"
        verdict_reason = (
            f"高さ制限（{height_limit_m}m）によりアンテナ高が社内基準未達ですが、"
            f"スモールセル×{alternative_small_cells}追加により"
            f"カバレッジ{alternative_coverage_pct}%（基準{coverage_standard_pct}%以上）を達成可能です。"
            f"追加コスト（{alternative_cost_delta}）の承認を条件に設置推奨します。"
        )
    else:
        verdict = "no_go"
        verdict_reason = "複数の重大な基準違反があります。代替案を再検討してください。"

    # ─── Recommended actions ────────────────────────────────────────────────
    actions = []
    if verdict == "conditional_go":
        actions.append(
            f"スモールセル×{alternative_small_cells}の追加コスト（{alternative_cost_delta}、工期{alternative_timeline_delta}）について経営承認を取得する"
        )
        actions.append("A市景観条例に定めるアースブラウン/グレー外装色で設計書を更新する")
        actions.append("住民説明会で取得済みの同意書を工事申請書類に添付する")
        actions.append("騒音対策計画書をA市担当部署に提出する")
    elif verdict == "no_go":
        actions.append("代替サイトの探索を開始する")
        actions.append("自治体と高さ制限の例外申請可能性を協議する")

    # ─── Sources ────────────────────────────────────────────────────────────
    sources = []
    for email in emails:
        sources.append({
            "type": "email",
            "title": email["subject"],
            "date": email["date"],
            "author": email["from"],
        })
    for meeting in meetings:
        sources.append({
            "type": "meeting",
            "title": meeting["title"],
            "date": meeting["date"],
            "author": "、".join(meeting.get("participants", [])),
        })
    for doc in documents:
        sources.append({
            "type": "document",
            "title": doc["title"],
            "date": doc["date"],
            "author": doc.get("author", ""),
        })

    return {
        "verdict": verdict,
        "verdict_reason": verdict_reason,
        "checks": checks,
        "alternatives": alternatives,
        "actions": actions,
        "sources": sources,
        # Additional numeric summary for UI cards
        "summary": {
            "coverage_current_pct": coverage_current_pct,
            "coverage_standard_pct": coverage_standard_pct,
            "coverage_alternative_pct": alternative_coverage_pct,
        },
    }
