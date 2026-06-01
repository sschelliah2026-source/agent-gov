Title: agent-gov-saas: Open-source AI agent cost governance proxy (Python, FastAPI, pip install)

Subreddit: r/Python

Body:

I built a Python package that acts as a reverse proxy for AI agent tool calls — it checks budgets, tracks per-tool costs, and auto-pauses agents that overspend.

**Why:** A recursive AI agent on our team ran up a ₹5,000 ($60) GPT-4 bill in one night. Needed a way to prevent this that didn't require modifying every agent. A library can be monkey-patched, removed, or forgotten. A proxy is a network boundary — you can't bypass it from inside the agent.

**How it works:**
```
Agent → agent-gov proxy → checks budget & tool cost → ✅ 200: proceed / 🛑 429: auto-paused
```

**Install in 30 seconds:**
```bash
pip install agent-gov-saas
agent-gov start
```

**Register an agent with a daily budget:**
```bash
curl -X POST http://localhost:8000/agents/register \
  -H "Content-Type: application/json" \
  -d '{"name": "My Bot", "daily_budget": 500}'
```

**Features:**
- Per-agent daily budgets with auto-pause
- Tool registry with real per-call costs (GPT-4o: ₹15, DeepSeek: ₹1, Firecrawl: ₹50)
- Proxy uses registered tool cost, not client estimate (prevents lying about costs)
- Daily auto-reset at midnight
- Multi-tenant workspaces for teams
- Live HTML dashboard with per-agent and per-tool spend
- 24 pre-configured tool presets (LLMs, web search, comms, media gen, code exec)
- CLI with `agent-gov start / status / version`
- Docker Compose support
- 45 tests, 0.3s runtime

**Tech:** FastAPI + SQLite + Jinja2. Dependencies are minimal — FastAPI, SQLite (via aiosqlite), Jinja2. Zero cloud dependencies.

**GitHub:** https://github.com/sschelliah2026-source/agent-gov
**PyPI:** https://pypi.org/project/agent-gov-saas/
**License:** MIT

Happy to answer questions! What tools would you want pre-configured?
