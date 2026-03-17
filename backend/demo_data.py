# Demo data for the base station compliance checker
# Simulates data that would be retrieved from M365 via Work IQ

SITES = [
    {
        "id": "site-2026-0001",
        "name": "A市中央公園 (Site-2026-0001)",
        "location": "A市中央区",
        "type": "公園用地",
    },
    {
        "id": "site-2026-0002",
        "name": "B市商業地区 (Site-2026-0002)",
        "location": "B市西区",
        "type": "商業用地",
    },
    {
        "id": "site-2026-0003",
        "name": "C町工業団地 (Site-2026-0003)",
        "location": "C町北部",
        "type": "工業用地",
    },
]

# Mock M365 data for site-2026-0001 (A市中央公園)
MOCK_M365_DATA = {
    "site-2026-0001": {
        "emails": [
            {
                "id": "email-001",
                "from": "中村 健一",
                "subject": "【A市公園用地】自治体条件の確認結果",
                "date": "2026-05-12",
                "type": "email",
                "body": (
                    "A市景観条例に基づく高さ制限は15mです。外装色はA市指定のアースブラウンまたはグレーに限ります。"
                    "住民説明会は5月10日に実施済みで、住民代表の同意書を取得しています。"
                    "自治体担当者は工事期間中の騒音対策を要求しています。"
                ),
                "extracted": {
                    "height_limit_m": 15,
                    "appearance_color": "市指定色（アースブラウン/グレー）",
                    "resident_meeting_done": True,
                    "resident_meeting_date": "2026-05-10",
                    "municipality_conditions": ["高さ制限15m", "外装色指定", "住民説明会実施済み", "騒音対策要求"],
                },
            },
            {
                "id": "email-002",
                "from": "鈴木 大介",
                "subject": "【A市公園用地】RF設計からの技術制約",
                "date": "2026-05-15",
                "type": "email",
                "body": (
                    "RF設計の観点から、必要アンテナ高は20mです。高さ15mに制限した場合、"
                    "カバレッジは目標エリアの85%となり、社内基準95%を下回ります。"
                    "代替案として敷地内スモールセル2基を追加することで97%に回復可能です。"
                    "スモールセル追加のコストは約350万円増、工期は+2週間の見込みです。"
                ),
                "extracted": {
                    "required_antenna_height_m": 20,
                    "coverage_at_15m_pct": 85,
                    "coverage_target_pct": 95,
                    "alternative_small_cells": 2,
                    "alternative_coverage_pct": 97,
                    "alternative_cost_delta": "+350万円",
                    "alternative_timeline_delta": "+2週間",
                },
            },
        ],
        "meetings": [
            {
                "id": "meeting-001",
                "title": "A市基地局設置 設計会議 議事録",
                "date": "2026-05-18",
                "type": "meeting",
                "participants": ["中村 健一", "鈴木 大介", "田中 部長"],
                "body": (
                    "中村: 自治体は15mを厳守とのことです。景観条例の例外申請は困難です。\n"
                    "鈴木: スモールセル2基の追加で技術的には対応可能ですが、コストが増えます。\n"
                    "田中: スモールセル案のコスト判断は次回会議で決定します。"
                ),
                "extracted": {
                    "municipality_height_strict": True,
                    "exception_application_possible": False,
                    "small_cell_technically_feasible": True,
                    "cost_decision_pending": True,
                },
            },
        ],
        "documents": [
            {
                "id": "doc-001",
                "title": "基地局設置基準書 v3.2",
                "date": "2026-03-01",
                "type": "document",
                "author": "技術部",
                "body": (
                    "第3条 カバレッジ基準: 対象エリアにおけるカバレッジ率は95%以上とする。\n"
                    "第5条 住民説明会: 設置前に住民説明会を実施し、同意書を取得すること。\n"
                    "第7条 自治体条例準拠: 設置場所の自治体条例に完全準拠すること。\n"
                    "第9条 外装基準: 景観への配慮から、市区町村指定の色彩基準に従うこと。\n"
                    "第11条 代替案: 主案が基準未達の場合、代替案を検討し承認を得ること。"
                ),
                "extracted": {
                    "coverage_standard_pct": 95,
                    "resident_meeting_required": True,
                    "municipality_compliance_required": True,
                    "appearance_standard_required": True,
                    "alternative_approval_required": True,
                },
            },
        ],
    }
}

# Corporate standards (from design document)
CORPORATE_STANDARDS = {
    "coverage_min_pct": 95,
    "resident_meeting_required": True,
    "municipality_compliance_required": True,
    "appearance_standard_required": True,
}
