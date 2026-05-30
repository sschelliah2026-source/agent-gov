# 🛡 agent-gov

**AI Agent Cost Governance Platform**

[![PyPI version](https://img.shields.io/pypi/v/agent-gov-saas.svg)](https://pypi.org/project/agent-gov-saas/)
[![Python versions](https://img.shields.io/pypi/pyversions/agent-gov-saas.svg)](https://pypi.org/project/agent-gov-saas/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

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

### 1. Install

```bash
pip install agent-gov-saas
```

### 2. Start the server

```bash
agent-gov start
```

Server starts at `http://localhost:8000`.

> Alternatively, use Docker: `docker compose up` (see [GitHub repo](https://github.com/sschelliah2026-source/agent-gov) for docker-compose.yml).

### 3. Register an Agent

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

### 4. Route Agent Calls Through the Proxy

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

### 5. Watch the Dashboard

Open `http://localhost:8000/dashboard` — live view of all agents, their spend, and budget status.

### 6. (Optional) Pre-Register Common Tools

```bash
# Register 24 common AI tools with realistic costs (₹)
python seed_tools.py

# Preview before registering:
python seed_tools.py --list
```

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Health check + stats |
| `POST` | `/agents/register` | Create agent, get API key |
| `POST` | `/proxy/call` | Proxy a tool call (budget checking + real cost lookup) |
| `POST` | `/agents/{key}/resume` | Resume a paused agent (resets budget) |
| `POST` | `/agents/{key}/reset` | Reset daily budget counters (no unpause) |
| `POST` | `/workspaces` | Create a workspace (returns API key) |
| `GET` | `/workspaces` | List all workspaces |
| `POST` | `/tools/register` | Register a tool with its known cost per call |
| `GET` | `/tools` | List all registered tools |
| `GET` | `/analytics/tools` | Per-tool spend statistics |
| `GET` | `/dashboard` | Live HTML dashboard |
| `GET` | `/docs` | Interactive OpenAPI docs (Swagger) |

---

## Features

| Feature | What it does |
|---|---|
| **Budget enforcement** | Auto-pause agents that exceed their daily budget |
| **Tool registry** | Register tools with known costs — agents can't lie about pricing |
| **Real cost lookup** | Proxy uses registered tool cost, not client estimate |
| **Per-tool analytics** | See spend broken down by tool, not just by agent |
| **Daily auto-reset** | Budgets reset automatically at midnight |
| **Multi-tenancy** | Workspaces for teams, projects, or clients |
| **Dashboard** | Live HTML dashboard with per-agent and per-tool views |
| **CLI** | `agent-gov start` / `status` / `version` |
| **Docker** | Ready-to-run Docker Compose setup |

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

## Technology Stack

| Component | Technology | Why |
|---|---|---|
| API Framework | FastAPI | Fast, async, auto-docs |
| Validation | Pydantic | Type-safe input validation |
| Server | Uvicorn | Production ASGI server |
| Storage | SQLite via aiosqlite | Persistent, zero setup |
| Templates | Jinja2 | Server-rendered dashboard |
| Tool Registry | SQLite + UPSERT | Known tool costs, agents can't lie |
| Workspaces | SQLite + migrations | Multi-tenancy with workspace isolation |
| Testing | pytest + httpx | Fast, isolated tests |

---

## License

MIT
