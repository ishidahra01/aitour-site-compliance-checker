# 基地局設置チェッカー

CXO向けデモ用Webアプリ「基地局設置チェッカー」— GitHub Copilot SDK × Work IQ MCP × M365 Copilotの3層連携（Openness Proof）を実証するデモアプリです。

[Architecture Details](docs/architecture.md)

## Overview

PMが対象サイトを選んでボタンを押すと、GitHub Copilot SDKがWork IQ MCP経由でM365上の散在データ（メール・会議録・設計基準書）を収集・突合し、適合性レポートを画面に表示します。

チェックの流れ:

1. Work IQ MCPツールで自治体条件・RF設計制約・設置基準書・代替案情報を収集する。
2. ルールベースの `site_standards_checker` ツールでカバレッジ基準・アンテナ高さ条例・自治体条件を突合する。
3. 判定結果（GO / 条件付き GO / NO-GO）とチェック詳細・推奨アクションをUIに表示する。

## Architecture

```
Browser
 -> Next.js 単一ページUI（SiteCheckerInterface） (port 3000)
 -> FastAPI Backend (port 8000)
    |- POST /api/check           — チェックジョブ作成
    `- GET  /api/check/{id}/stream — SSEでログ・結果をストリーム
       -> CheckAgent (GitHub Copilot SDK)
          |- Session-level MCP server: Work IQ (@microsoft/workiq@latest)
          `- Local tool: site_standards_checker (rule-based Python)
```

## Quick Start

### Prerequisites

| Requirement | Details |
|-------------|---------|
| GitHub Copilot subscription または BYOK | バックエンドがGitHub Copilot SDKを使用します。 |
| Copilot CLI | `gh extension install github/gh-copilot` |
| Node.js 18+ | フロントエンドとWork IQ MCPサーバーに必要です。 |
| Python 3.11+ | バックエンドに必要です。 |
| Work IQ access | 実データを使ったデモに必要です（無効化も可）。 |

### 1. Clone and configure

```bash
git clone https://github.com/ishidahra01/aitour-site-compliance-checker.git
cd aitour-site-compliance-checker
cp .env.example .env
```

### 2. Backend setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

バックエンドAPIは `http://localhost:8000` でリッスンします。

### 3. Frontend setup

```bash
cd frontend
npm install
npm run dev
```

アプリは `http://localhost:3000` で利用できます。

### 4. Authenticate Copilot and Work IQ

```bash
gh extension install github/gh-copilot
gh auth login
gh copilot --version

npm install -g @microsoft/workiq
workiq login
```

`WORKIQ_ENABLED=true` の場合、バックエンドは各チェックジョブのCopilotセッションにWork IQをMCPサーバーとして接続します。

## Environment Variables

最低限の設定:

```env
COPILOT_GITHUB_TOKEN=ghp_your_github_token
WORKIQ_ENABLED=true
```

または `gh auth login` でGitHub CLIを認証して `COPILOT_GITHUB_TOKEN` を省略できます。

オプション（BYOK）:

```env
BYOK_PROVIDER=azure
BYOK_API_KEY=your_key
BYOK_BASE_URL=https://your-resource.openai.azure.com
BYOK_MODEL=gpt-4o
BYOK_AZURE_API_VERSION=2024-10-21
```

## Demo Flow

1. サイト選択プルダウンで「A市中央公園 (Site-2024-0847)」を選択する。
2. チェック項目（自治体条件突合・設計基準チェック・代替案分析・コスト試算）をトグルで選択する（または追加指示フィールドに自由入力する）。
3. 「✓ 適合性チェックを実行」ボタンを押す。
4. エージェントログエリアにWork IQクエリや処理状況がリアルタイム表示される。
5. チェック完了後、結果エリアに判定バッジ・数値カード・チェック結果テーブル・推奨アクション・情報ソースが表示される。

エージェントログの表示例:

```
Copilot SDK セッション開始 (model: gpt-4o)
MCP: Work IQ connected ✓
Work IQ クエリ: "A市基地局 自治体条件"
  → データ取得完了
Work IQ クエリ: "A市基地局 設計要件"
  → データ取得完了
site-standards-checker ツールを実行中...
レポート生成完了 ✓
```

## UI Features

| 機能 | 説明 |
|------|------|
| サイト選択プルダウン | A市中央公園など3件のデモサイトから選択。 |
| チェック項目トグル | 自治体条件突合 / 設計基準チェック / 代替案分析 / コスト試算を個別ON/OFF。 |
| 追加指示フィールド | 自由入力するとエージェントへの指示が上書きされる。 |
| エージェントログ | 黒背景・モノスペース、SSEで1行ずつリアルタイム表示。 |
| 判定バッジ | `GO`（緑）/ `条件付き GO`（黄）/ `NO-GO`（赤）を大きく表示。 |
| カバレッジ数値カード | 現状 / 社内基準 / 代替案適用後の3枚。 |
| チェック結果テーブル | 4列（項目 / 基準 / 現状 / 判定）、pass=緑・fail=赤・constraint=黄バッジ。 |
| 推奨アクション | 番号付きリスト。 |
| 情報ソース | 参照したM365データソースをピル形式で表示。 |

## Project Structure

```
.
|- backend/
|  |- main.py              — FastAPI エントリポイント（/api/check, /api/check/{id}/stream, レガシー endpoints）
|  |- check_agent.py       — CheckAgent: Copilot SDKセッション管理・ジョブキュー
|  |- agent.py             — SupportAgent: レガシーチャットエージェント
|  |- requirements.txt
|  |- generated_reports/   — PowerPointレポート出力先（レガシー）
|  |- skills/
|  |  |- checker-skills/
|  |  |  `- site-checker/
|  |  |     `- SKILL.md    — site_standards_checker 呼び出しワークフロー指示
|  |  |- site_checker.py   — スキルディレクトリパス定義
|  |  `- site_approval.py  — レガシー承認ワークフロースキル
|  `- tools/
|     |- site_checker_tool.py  — site_standards_checker ルールベースツール
|     `- pptx_tool.py          — generate_powerpoint_tool（レガシー）
|- docs/
|  `- architecture.md
|- frontend/
|  |- app/
|  |  |- components/
|  |  |  `- SiteCheckerInterface.tsx  — メインUIコンポーネント
|  |  |- lib/
|  |  |  |- api.ts     — submitCheck / getCheckStreamUrl
|  |  |  `- types.ts   — CheckResult, LogEvent 等の型定義
|  |  |- layout.tsx
|  |  `- page.tsx
|  |- package.json
|  `- tsconfig.json
|- .env.example
`- README.md
```

## API Reference

### 基地局設置チェッカー API

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/check` | チェックジョブを作成し `check_id` を返す |
| `GET` | `/api/check/{id}/stream` | SSEでエージェントログと最終結果をストリーム |

#### POST /api/check

リクエスト:

```json
{
  "site_id": "Site-2024-0847",
  "check_items": ["自治体条件突合", "設計基準チェック", "代替案分析", "コスト試算"],
  "free_text": "（任意）追加の指示"
}
```

レスポンス:

```json
{ "check_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" }
```

#### GET /api/check/{id}/stream

SSEイベント:

```json
{ "type": "log",    "message": "Work IQ クエリ: \"A市基地局 自治体条件\"" }
{ "type": "result", "data": { "verdict": "conditional_go", "verdict_reason": "...", ... } }
{ "type": "error",  "message": "エラー内容" }
```

#### CheckResult JSON スキーマ

```typescript
interface CheckResult {
  verdict: "go" | "conditional_go" | "no_go";
  verdict_reason: string;
  checks: {
    item: string;
    standard: string;
    current: string;
    status: "pass" | "fail" | "constraint";
  }[];
  alternatives: {
    name: string;
    coverage: string;
    cost_delta: string;
    timeline_delta: string;
  }[];
  actions: string[];
  sources: {
    type: "email" | "meeting" | "document";
    title: string;
    date: string;
    author: string;
  }[];
  coverage: {
    current: number;
    standard: number;
    alternative: number | null;
  };
}
```

### その他のエンドポイント

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | ヘルスチェック |
| `GET` | `/models` | 利用可能なCopilotモデル一覧 |

## Extending the Agent

新しいチェックルールを追加するには:

1. `backend/tools/site_checker_tool.py` の `site_standards_checker` 関数にルールを追加する。
2. 必要に応じて `SiteStandardsCheckerParams` モデルにパラメータを追加する。

エージェントのクエリ戦略を変更するには:

- `backend/skills/checker-skills/site-checker/SKILL.md` を編集する。

## References

- [GitHub Copilot SDK](https://github.com/github/copilot-sdk)
- [GitHub Copilot SDK Cookbook](https://github.com/github/awesome-copilot/tree/main/cookbook/copilot-sdk)
- [Work IQ MCP](https://github.com/microsoft/work-iq-mcp)
- [Model Context Protocol](https://modelcontextprotocol.io)

## License

MIT - see [LICENSE](LICENSE)
