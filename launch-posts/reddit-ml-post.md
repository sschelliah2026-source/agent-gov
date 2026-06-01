Title: agent-gov: Open-source AI agent cost governance proxy with per-tool tracking and auto-pause

Subreddit: r/MachineLearning

Body:

I built a tool that saved me from a ₹5,000 ($60) GPT-4 bill caused by a recursive agent loop, and I'm sharing it in case others face the same problem.

**The problem:** AI agents call expensive tools (LLMs, browsers, APIs, email). Without controls:
- A recursive agent burns ₹5,000 ($60) in one night on GPT-4
- A buggy loop sends 10,000 emails before you notice
- You discover the bill when your credit card statement arrives

**What agent-gov does:** A lightweight reverse proxy that sits between your agents and their tools. Every call goes through it — budgets are checked, costs are tracked per-tool, and agents that overspend are auto-paused.

**Key features:**
- Per-agent daily budgets with auto-pause on overage
- Tool registry with REAL costs (agents can't fake their estimates)
- Proxy looks up registered tool cost, not client estimate
- Daily auto-reset at midnight
- Multi-tenant workspaces for teams
- Live HTML dashboard with per-agent and per-tool spend
- 24 pre-configured tool presets with realistic costs
- CLI: `agent-gov start / status / version`
- Docker Compose support

**Tech stack:** Python, FastAPI, SQLite, Jinja2, pytest (45 tests, 0.3s runtime)

**Quick start:**
```bash
pip install agent-gov-saas
agent-gov start
```

Then register agents and tools via the API, route calls through the proxy on port 8000.

**GitHub:** https://github.com/sschelliah2026-source/agent-gov
**PyPI:** https://pypi.org/project/agent-gov-saas/

Built as an open-source MIT project over the last week. Would love feedback on what other integrations would be useful.
