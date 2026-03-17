# Architecture Deep Dive

## Component Diagram

```
Browser
  -> Next.js SiteCheckerInterface（単一ページ）
  -> REST + SSE
  -> FastAPI backend
     |- POST /api/check           — チェックジョブ作成
     `- GET  /api/check/{id}/stream — SSEストリーム
        -> CheckAgent (GitHub Copilot SDK)
           |- Session-level MCP server: Work IQ (@microsoft/workiq@latest)
           `- Local Python tool: site_standards_checker（ルールベース）
```

## Core Components

| Component | Technology | Responsibility |
|-----------|------------|----------------|
| Frontend | Next.js + React (TypeScript) | 単一ページUI（サイト選択・チェック項目トグル・自由入力）、SSEでログ・結果をリアルタイム表示 |
| Backend API | FastAPI + SSE | チェックジョブ作成（REST）、エージェントログ・結果のSSEストリーム |
| Check Agent runtime | GitHub Copilot SDK | ジョブごとにCopilotセッションを作成、Work IQ MCPを接続、site_standards_checkerツールを登録 |
| Organizational context | Work IQ MCP | M365上のメール・会議録・SharePoint文書をCopilotセッションに直接公開 |
| Compliance checker | `site_standards_checker` (Python) | カバレッジ基準・アンテナ高さ条例・自治体条件をルールベースで突合し構造化JSONを返す |

## Runtime Flow

### 1. チェックジョブ作成

フロントエンドが `POST /api/check` を呼び出すと:

1. `CheckAgent.create_job()` が `CheckJob`（check_id, site_id, check_items, free_text, asyncio.Queue）を生成する。
2. `asyncio.create_task()` でバックグラウンドジョブを開始し、即座に `{ "check_id": "..." }` を返す。

### 2. エージェント実行フロー

```
POST /api/check → check_id を返す
  -> CheckAgent._run_job(job)
     -> CopilotClient.create_session(session_id, model, skill_directories, tools=[site_standards_checker], mcp_servers={workiq})
     -> session.send(prompt)
        -> モデルがWork IQ MCPツールを呼び出してデータ収集
        -> モデルが site_standards_checker を呼び出して突合・判定
     -> on_event() でSDKイベントをlog_queueへエンキュー
```

### 3. SSEストリーム

フロントエンドが `GET /api/check/{id}/stream` を開くと:

- `job.log_queue` からメッセージを取り出してSSEイベントとして送出する。
- `None`（sentinel）を受信するとストリームを終了する。

送出するイベント:

```json
{ "type": "log",    "message": "Work IQ クエリ: \"A市基地局 自治体条件\"" }
{ "type": "result", "data": { "verdict": "conditional_go", ... } }
{ "type": "error",  "message": "エラー内容" }
```

### 4. SDK イベントハンドリング

`check_agent.py` の `on_event()` ハンドラが以下のSDKイベントを処理する:

| SDK Event | 処理内容 |
|-----------|---------|
| `tool.execution_start` (site_standards_checker) | "site-standards-checker ツールを実行中..." をキューへ |
| `tool.execution_start` (その他) | Work IQクエリメッセージをキューへ |
| `tool.execution_complete` (site_standards_checker) | レポート生成完了メッセージ、結果JSONをパースして `result` イベントへ |
| `tool.execution_complete` (その他) | "データ取得完了" をキューへ |
| `session.idle` | done_eventをセットしてジョブ完了 |

## Tool Model

### Work IQ MCP

- 各チェックジョブのCopilotセッションに `mcp_servers` 設定で接続
- `npx -y @microsoft/workiq@latest mcp` として起動
- `WORKIQ_ENABLED=false` の場合は接続しない（デモデータへのフォールバック）

### site_standards_checker

- `backend/tools/site_checker_tool.py` に実装
- Copilot SDK の `@define_tool` デコレータで登録
- 入力: `SiteStandardsCheckerParams`（カバレッジ値・アンテナ高さ・自治体条件・代替案情報・ソース一覧）
- 出力: 構造化JSON（verdict / verdict_reason / checks / alternatives / actions / sources / coverage）
- LLM判定ではなく固定ルールで突合する

## Job Lifecycle

- `CheckJob` は `check_id`・`site_id`・`check_items`・`free_text`・`asyncio.Queue`・`result` を保持する
- ジョブはメモリ内の辞書 (`_jobs`) に格納される
- バックエンドを再起動するとすべてのジョブが消去される

## Skill Configuration

`backend/skills/checker-skills/site-checker/SKILL.md` がエージェントの動作を制御する:

- Work IQ MCPへのクエリを英語で実行するよう指示
- 収集した情報をもとに `site_standards_checker` ツールを呼び出すよう指示

## Configuration

環境変数一覧:

| Variable | Purpose |
|----------|---------|
| `COPILOT_GITHUB_TOKEN` | Copilot認証用GitHubトークン（省略可） |
| `COPILOT_CLI_PATH` | Copilot CLIの明示的パス（省略可） |
| `WORKIQ_ENABLED` | Work IQ MCPを接続する（`true` / `false`） |
| `BYOK_PROVIDER` | BYOKモードを有効化（`openai` / `azure` / `anthropic`） |
| `BYOK_BASE_URL` | モデルプロバイダーエンドポイント |
| `BYOK_API_KEY` | モデルプロバイダーAPIキー |
| `BYOK_MODEL` | 使用するモデル名（デフォルト: `gpt-4o`） |
| `BYOK_AZURE_API_VERSION` | Azure BYOK APIバージョン |
| `BACKEND_HOST` | FastAPIバインドホスト |
| `BACKEND_PORT` | FastAPIバインドポート |
| `CORS_ORIGINS` | 許可するフロントエンドオリジン |

## Design Notes

- コンプライアンス判定はLLMではなくルールベースのPythonコードで実施し、判定の再現性を確保している。
- Work IQのデータアクセスはMCPに委譲しており、Pythonラッパーは存在しない。
- フロントエンドはSSEのみを使用し、WebSocketは使用しない（チェッカーUIの場合）。
- 旧来のチャットUI・WebSocketエンドポイントはレガシーとして残存しているが、メインデモでは使用しない。
