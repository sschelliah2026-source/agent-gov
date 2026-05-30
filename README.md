# 🛡 agent-gov

**AI Agent Cost Governance Platform**

A reverse proxy that tracks, budgets, and controls what your AI agents spend. Like a credit card with limits — but for your agents.

---

## What Problem Does This Solve?

AI agents call expensive tools (LLMs, browsers, APIs, email services). Without controls:

- A recursive agent burns ₹5,000 in one night on GPT-4
- A buggy loop sends 10,000 emails before you notice
- You discover the bill when your credit card statement arrives

**agent-gov** sits between your agents and their tools. Every call goes through us. We check budgets, track costs, and auto-pause overspending agents.

---

## Quick Start

### 1. Install & Run

```bash
git clone <repo-url>
cd agent-gov
python3 -m venv venv
source venv/bin/activate
pip install fastapi uvicorn pydantic httpx
python app.py
```

Server starts at `http://localhost:8000`.

### 2. Register an Agent

```bash
curl -X POST http://localhost:8000/agents/register \
  -H "Content-Type: application/json" \
  -d '{"name": "My Bot", "daily_budget": 500}'
```

Response:
```json
{
  "api_key": "ag-abc123...",
  "name": "My Bot",
  "daily_budget": 500,
  "message": "Save this API key — it won't be shown again!"
}
```

### 3. Route Agent Calls Through the Proxy

Instead of calling tools directly, your agent calls our proxy:

```python
# BEFORE (no governance):
response = call_openai(prompt)

# AFTER (with agent-gov):
gov_response = requests.post("http://localhost:8000/proxy/call", json={
    "agent_key": "ag-abc123...",
    "tool_name": "openai-gpt4",
    "estimated_cost": 12.50   # ₹12.50 for this call
})
if gov_response.status_code == 429:
    print("Budget exceeded! Agent auto-paused.")
else:
    response = call_openai(prompt)  # Proceed with actual call
```

### 4. Watch the Dashboard

Open `http://localhost:8000/dashboard` — live view of all agents, their spend, and budget status.

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|---|
| `GET` | `/` | Health check + stats (includes tool count) |
| `POST` | `/agents/register` | Create agent, get API key |
| `POST` | `/proxy/call` | Proxy a tool call (budget checking + real cost lookup) |
|| `POST` | `/agents/{key}/resume` | Resume a paused agent (resets budget) |
|| `POST` | `/agents/{key}/reset` | Reset daily budget counters (no unpause) |
|| `POST` | `/workspaces` | Create a workspace (returns API key) |
|| `GET` | `/workspaces` | List all workspaces |
|| `POST` | `/tools/register` | Register a tool with its known cost per call (scoped to workspace) |
| `GET` | `/tools` | List all registered tools |
| `GET` | `/analytics/tools` | Per-tool spend statistics |
| `GET` | `/dashboard` | Live HTML dashboard (agents + per-tool breakdown) |
| `GET` | `/docs` | Interactive OpenAPI docs (Swagger) |

### POST /agents/register

```json
{
  "name": "string (1-100 chars, required)",
  "daily_budget": "float (positive, required)"
}
```

### POST /proxy/call

```json
{
  "agent_key": "string (required)",
  "tool_name": "string (required)",
  "estimated_cost": "float (default: 0)"
}
```

**Responses:**
- `200` — Call approved
- `401` — Invalid API key
- `429` — Budget exceeded / agent paused

### POST /agents/{api_key}/resume

Resume a paused agent. Resets daily spend to 0.

---

## Architecture

```
Agent (your code)
    │
    │ POST /proxy/call { agent_key, tool_name, estimated_cost }
    ▼
┌──────────────────────────────┐
│         agent-gov             │
│                                │
│  1. Auth: Is key valid?       │
│  2. Budget: Will this exceed? │
│  3. Log: Track cost + tool    │
│                                │
│  If approved → return 200     │
│  If denied  → return 429     │
└──────────────────────────────┘
    │
    │ Agent calls actual tool
    ▼
┌──────────────────────────────┐
│   Actual Tool (OpenAI, etc.)  │
└──────────────────────────────┘
```

---

## Budget Enforcement Rules

| Condition | Status Code | Behavior |
|---|---|---|
| Valid key, under budget | 200 | Approved |
| Invalid API key | 401 | Rejected |
| Call would exceed budget | 429 | Rejected + **auto-pause** |
| Agent is paused | 429 | Rejected |

Auto-paused agents must be manually resumed via `/agents/{key}/resume`.

---

## Technology Stack

|| Component | Technology | Why |
|---|---|---|---|
|| API Framework | FastAPI | Fast, async, auto-docs |
|| Validation | Pydantic | Type-safe input validation |
|| Server | Uvicorn | Production ASGI server |
|| Storage | SQLite via aiosqlite | Persistent, zero setup |
|| Templates | Jinja2 | Server-rendered dashboard |
|| Tool Registry | SQLite + UPSERT | Tools have known costs, agents can't lie |
|| Workspaces | SQLite + migrations | Multi-tenancy with workspace isolation |
|| Testing | pytest + httpx | Fast, isolated tests |

---

## Running Tests

```bash
cd agent-gov
source venv/bin/activate
pip install pytest httpx
python -m pytest test_app.py -v
```

**45 tests covering:**
- Agent registration + validation + workspace scoping
- Proxy approval flow
- Budget enforcement + auto-pause + auto-reset
- Resume functionality
- Reset endpoint (manual, paused agent, not found)
- Invalid key rejection
- Dashboard rendering + per-tool breakdown + reset info + workspace filter
- Health checks with tool count
- Edge cases (zero cost, exact budget, large/small values)
- Tool registry (register, update, list, validation, workspace isolation)
- Real cost lookup (registered tool, fallback to estimate, budget enforcement)
- Per-tool analytics + workspace filter
- Daily budget auto-reset (midnight boundary, no spurious reset)
- Workspace CRUD (create, list, default exists)
- Agent/tool workspace isolation
- Backward compatibility (default workspace)

---

## Roadmap

| Phase | What | Status |
|---|---|---|---|
| v0.1 | Core proxy + in-memory storage | ✅ Done |
| v0.2 | SQLite persistence | ✅ Done |
| v0.3 | Tool registry + real cost tracking | ✅ Done |
| v0.4 | Daily budget auto-reset | ✅ Done |
| v0.5 | Multi-tenancy (workspaces) | ✅ Done |
| v1.0 | Open-source release | 🔜 Next |

---

## License

MIT
