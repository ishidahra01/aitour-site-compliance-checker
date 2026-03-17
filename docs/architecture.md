# Architecture Deep Dive

## Component Diagram

```
Browser
  -> Next.js chat UI
  -> WebSocket / REST
  -> FastAPI backend
  -> Site Approval Bot (GitHub Copilot SDK)
     |- Local Python tool: generate_powerpoint_tool
     `- Optional session-level MCP server: Work IQ
```

## Core Components

| Component | Technology | Responsibility |
|-----------|------------|----------------|
| Frontend | Next.js + React | Chat UX, streaming display, approval report panel, tool execution cards |
| Backend API | FastAPI + WebSocket | Session creation, event streaming, report downloads |
| Agent runtime | GitHub Copilot SDK | Manages Copilot sessions, forwards prompts, streams tool and model events |
| Organizational context | Work IQ MCP | Exposes Microsoft 365 data sources directly to the Copilot session |
| Report generation | `python-pptx` | Builds downloadable `.pptx` summaries |

## Runtime Flow

### 1. Session startup

`backend/agent.py` creates a `CopilotClient` and, when `WORKIQ_ENABLED=true`, attaches Work IQ as a session-level MCP server.

Only one local custom tool is registered today:

- `generate_powerpoint_tool`

### 2. User message flow

```
Browser sends { prompt, model }
  -> FastAPI websocket endpoint
  -> SupportAgent.send_message(...)
  -> Copilot session receives the prompt
  -> Model calls Work IQ MCP tools as needed
  -> Model may call generate_powerpoint_tool
  -> Events stream back to the browser
```

### 3. Event streaming

The backend listens to Copilot SDK events and normalizes them into frontend-friendly JSON payloads:

- `assistant.message_delta`
- `assistant.message`
- `tool.execution_start`
- `tool.execution_complete`
- `session.idle`
- `error`

These events drive the message stream, tool execution cards, and approval report panel.

## Tool Model

### Work IQ MCP

- Attached directly to each Copilot session through `mcp_servers`
- Started with `npx -y @microsoft/workiq ... mcp`
- Tool names come from the Work IQ server itself
- No Python wrapper exists in this repository

### generate_powerpoint_tool

- Implemented in `backend/tools/pptx_tool.py`
- Uses `python-pptx`
- Generates a slide deck in `backend/generated_reports/`
- Returns a download path consumed by `GET /reports/{filename}`

## Session Lifecycle

- The backend keeps one `CopilotSession` per chat `session_id`
- Sessions are stored in memory and reused across websocket messages
- Deleting a session destroys the underlying Copilot session
- Restarting the backend clears all in-memory sessions

## Configuration

Relevant environment variables:

| Variable | Purpose |
|----------|---------|
| `COPILOT_GITHUB_TOKEN` | Optional GitHub token for Copilot authentication |
| `COPILOT_CLI_PATH` | Optional explicit Copilot CLI path |
| `WORKIQ_ENABLED` | Enables the Work IQ MCP attachment |
| `BYOK_PROVIDER` | Enables BYOK mode |
| `BYOK_BASE_URL` | Model provider endpoint |
| `BYOK_API_KEY` | Model provider API key |
| `BYOK_AZURE_API_VERSION` | Azure BYOK API version |
| `BACKEND_HOST` | FastAPI bind host |
| `BACKEND_PORT` | FastAPI bind port |
| `CORS_ORIGINS` | Allowed frontend origins |

## Design Notes

- Work IQ access is intentionally delegated to MCP instead of custom Python wrappers.
- Local tool surface area is intentionally small; only PowerPoint generation is implemented in Python.
- The approval workflow lives in `backend/skills/site_approval.py`, which instructs the model to gather context from Work IQ before producing a report.
