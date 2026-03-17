# 基地局設置チェッカー

CXO向けデモ用Webアプリ「基地局設置チェッカー」です。  
**Work IQ × Copilot SDK × Agent 365** の3層連携（Openness Proof）を実証します。

PMが対象サイトを選んでボタンを押すと、Copilot SDKがWork IQ MCP経由でM365上の散在データ（メール・会議録・設計基準書）を収集・突合し、適合性レポートを画面に表示します。

---

## アーキテクチャ

```
┌─────────────┐      POST /api/check        ┌─────────────────────┐
│  Frontend   │ ─────────────────────────▶  │  FastAPI Backend    │
│ (HTML/JS)   │      GET /api/check/:id/    │  (Python)           │
│             │ ◀────── stream (SSE) ──────  │                     │
└─────────────┘                             │  Copilot SDK        │
                                            │    │                │
                                            │    ▼                │
                                            │  Work IQ MCP        │
                                            │  (@microsoft/workiq)│
                                            │    │                │
                                            │    ▼                │
                                            │  M365 Data          │
                                            │  (Outlook/Teams/SP) │
                                            └─────────────────────┘
```

## ディレクトリ構成

```
.
├── backend/
│   ├── main.py                  # FastAPI アプリ
│   ├── checker.py               # Copilot SDK セッション管理（モック対応）
│   ├── demo_data.py             # デモ用 M365 データ
│   ├── site_standards_checker.py # ルールベース適合性チェック（カスタムスキル実装）
│   └── requirements.txt
├── frontend/
│   └── index.html               # シングルページ UI
├── skills/
│   └── site-standards-checker/
│       └── SKILL.md             # Copilot SDK スキル定義
└── README.md
```

## セットアップ

### 前提条件

- Python 3.11+
- Node.js 18+ （Work IQ MCP サーバー起動に必要）

### インストール

```bash
cd backend
pip install -r requirements.txt
```

### 環境変数

| 変数名 | 説明 |
|--------|------|
| `GITHUB_TOKEN` | GitHub Copilot SDK 認証用トークン（未設定時はモックモードで動作） |

### 起動

```bash
cd backend
uvicorn main:app --reload --port 8000
```

ブラウザで http://localhost:8000 を開いてください。

---

## 動作モード

### モックモード（GITHUB_TOKEN 未設定）

Work IQ への実接続なしでデモを実行できます。A市中央公園 (Site-2026-0001) のデモデータを使用してリアルなログとチェック結果を表示します。

### リアルモード（GITHUB_TOKEN 設定済み）

実際の Copilot SDK セッションを起動し、Work IQ MCP 経由で M365 のデータを取得します。

```bash
export GITHUB_TOKEN=your_token_here
cd backend
uvicorn main:app --reload --port 8000
```

---

## API 仕様

### `POST /api/check`

適合性チェックを開始します。

**リクエスト:**
```json
{
  "site_id": "site-2026-0001",
  "check_items": ["municipality", "design_standards", "alternatives", "cost"]
}
```

**レスポンス:**
```json
{ "id": "uuid-of-job" }
```

### `GET /api/check/{id}/stream`

SSE でエージェントログをストリームします。

イベント形式:
- `{"type": "log", "text": "..."}` — ログ行
- `{"type": "done", "result": {...}}` — 完了 + 結果
- `{"type": "error", "text": "..."}` — エラー
- `{"type": "heartbeat"}` — キープアライブ

### `GET /api/check/{id}`

最終結果 JSON を返します（チェック完了後）。

### `GET /api/sites`

利用可能なサイト一覧を返します。

---

## カスタムスキル: `site-standards-checker`

`skills/site-standards-checker/SKILL.md` で定義されたスキルで、Copilot SDK セッションに登録されます。Work IQ から取得した自然言語データと設置基準書の内容を受け取り、ルールベースで突合・判定します（LLM 判定ではなくコードで比較）。

---

## デモシナリオ（A市中央公園）

| データ | 内容 |
|--------|------|
| 中村メール (5/12) | 高さ制限15m（景観条例）、外装色指定、住民説明会実施済み |
| 鈴木メール (5/15) | 必要アンテナ高20m、15m時カバレッジ85%、スモールセル×2で97%回復可能（+350万円、+2週間） |
| 設計会議議事録 (5/18) | 15m厳守、スモールセル技術的に可能だがコスト増、判断未決定 |
| 設置基準書 v3.2 | カバレッジ≥95%、住民説明会必須、自治体条例準拠、外装基準 |

**判定: 条件付き GO** — スモールセル×2追加コスト承認を条件に設置推奨