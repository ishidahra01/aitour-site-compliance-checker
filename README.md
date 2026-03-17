# Site Approval Bot

AI agent for municipality site approval workflows, built with GitHub Copilot SDK, Work IQ MCP, and a Next.js chat UI.

[Architecture Details](docs/architecture.md)

## Overview

This project automates the approval workflow for mobile base station site installation requests.

When a municipality permission email arrives, the agent:

1. Collects relevant organizational context through Work IQ MCP tools.
2. Analyzes municipality conditions, RF design constraints, and outstanding decisions.
3. Produces a structured site approval report for the right-hand panel.
4. Generates a PowerPoint summary on request.

## Architecture

```
User (municipality email or chat)
 -> Next.js Chat UI (port 3000)
 -> FastAPI Backend (port 8000)
 -> Site Approval Bot Agent (GitHub Copilot SDK)
    |- Session-level MCP server: Work IQ (`npx -y @microsoft/workiq ... mcp`)
    `- Local tool: generate_powerpoint_tool (`python-pptx`)
```

## Quick Start

### Prerequisites

| Requirement | Details |
|-------------|---------|
| GitHub Copilot subscription or BYOK | The backend uses GitHub Copilot SDK. |
| Copilot CLI | `gh extension install github/gh-copilot` |
| Node.js 18+ | Required for the frontend and Work IQ MCP server. |
| Python 3.11+ | Required for the backend. |
| Work IQ access | Required for live organizational context retrieval. |

### 1. Clone and configure

```bash
git clone https://github.com/ishidahra01/aitour-site-approval-bot.git
cd aitour-site-approval-bot
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

The backend API listens on `http://localhost:8000`.

### 3. Frontend setup

```bash
cd frontend
npm install
npm run dev
```

The chat UI is available at `http://localhost:3000`.

### 4. Authenticate Copilot and Work IQ

```bash
gh extension install github/gh-copilot
gh auth login
gh copilot --version

npm install -g @microsoft/workiq
workiq login
```

If `WORKIQ_ENABLED=true`, the backend attaches Work IQ as a session-level MCP server for each Copilot session.

## Environment Variables

Minimum configuration:

```env
COPILOT_GITHUB_TOKEN=ghp_your_github_token
WORKIQ_ENABLED=true
```

Or authenticate GitHub CLI with `gh auth login` and omit `COPILOT_GITHUB_TOKEN`.

Optional BYOK configuration:

```env
BYOK_PROVIDER=azure
BYOK_API_KEY=your_key
BYOK_BASE_URL=https://your-resource.openai.azure.com
BYOK_MODEL=gpt-4o
BYOK_AZURE_API_VERSION=2024-10-21
```

## Demo Flow

Example prompt:

> "新しい許可書メールが届きました。中村市と鈴木設計の担当者から必要な承認を集めてください。"

Expected agent flow:

1. Use Work IQ MCP tools to gather municipality coordination history, meeting notes, and design constraints.
2. Synthesize findings into a `site-approval-report` code block.
3. Generate a `.pptx` report when asked.

Example report shape:

```text
Site Approval Report
====================

Site: [Site name / location]
Triggered by: [Trigger event]
Date: [Date]

Municipality Conditions
-----------------------
- [Condition 1]: satisfied / pending / unknown

RF Design Conditions
--------------------
- [Condition 1]: satisfied / pending cost approval

Status Summary
--------------
- Municipality requirements: satisfied / partially satisfied / pending
- RF design: satisfied / pending cost approval / requires action

Recommended Actions
-------------------
1. [Action item] - Responsible: [Person/team]

Approval Required From
----------------------
- [Person 1] ([Role/reason])
```

## UI Features

| Feature | Description |
|---------|-------------|
| Streaming responses | Messages stream token-by-token as the model responds. |
| Approval report panel | Renders the `site-approval-report` block in a dedicated panel. |
| Tool execution cards | Displays MCP and local tool calls with arguments and results. |
| Download button | Appears automatically after PowerPoint generation. |
| Model selector | Switches between available Copilot models. |

## Project Structure

```
.
|- backend/
|  |- main.py
|  |- agent.py
|  |- requirements.txt
|  |- generated_reports/
|  |- skills/
|  |  |- __init__.py
|  |  `- site_approval.py
|  `- tools/
|     |- __init__.py
|     `- pptx_tool.py
|- docs/
|  `- architecture.md
|- frontend/
|  |- app/
|  |  |- components/
|  |  `- lib/
|  |- package.json
|  `- tsconfig.json
|- .env.example
`- README.md
```

## API Reference

### REST endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/models` | List available Copilot models |
| `POST` | `/sessions` | Create a new chat session |
| `DELETE` | `/sessions/{id}` | Delete a session |
| `GET` | `/reports/{filename}` | Download a generated PowerPoint |

### WebSocket

Endpoint: `ws://localhost:8000/ws/chat/{session_id}`

Client payload:

```json
{ "prompt": "Your question here", "model": "gpt-4o" }
```

Streaming events:

```json
{ "type": "assistant.message_delta", "content": "..." }
{ "type": "tool.execution_start", "tool_name": "generate_powerpoint_tool", "args": {...} }
{ "type": "tool.execution_complete", "tool_name": "generate_powerpoint_tool", "result": "..." }
{ "type": "assistant.message", "content": "..." }
{ "type": "session.idle" }
{ "type": "error", "message": "..." }
```

When Work IQ is enabled, additional `tool.execution_*` events come directly from the attached MCP tools.

## Extending the Agent

To add another local Python tool:

1. Create a new module in `backend/tools/`.
2. Export it from `backend/tools/__init__.py`.
3. Add it to the `tools` list in `backend/agent.py`.

To change the approval workflow, edit `backend/skills/site_approval.py`.

## References

- [GitHub Copilot SDK](https://github.com/github/copilot-sdk)
- [GitHub Copilot SDK Cookbook](https://github.com/github/awesome-copilot/tree/main/cookbook/copilot-sdk)
- [Work IQ MCP](https://github.com/microsoft/work-iq-mcp)
- [Model Context Protocol](https://modelcontextprotocol.io)

## License

MIT - see [LICENSE](LICENSE)
