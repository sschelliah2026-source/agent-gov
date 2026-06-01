Title: Show HN: agent-gov-saas – Open-source AI agent cost governance (reverse proxy for budgets)

Body:

We built agent-gov because an AI agent on our team ran up a ₹5,000 ($60) GPT-4 bill in one night. It was a recursive loop — the agent was calling itself, generating more tokens, calling again. By morning, the API bill had tripled.

That was the moment we realized: AI agents need budget controls the same way servers need rate limiters.

agent-gov is a lightweight reverse proxy that sits between your agents and their LLM/API tools. Every call goes through it — it checks budgets, tracks costs per-tool, and auto-pauses agents that overspend.

What it does:
- Register agents with daily budgets
- Register tools with their real per-call cost (GPT-4o: ₹15, DeepSeek: ₹1, Firecrawl: ₹50/page)
- Proxy checks REAL tool cost, not what the agent claims
- Auto-pause agents when budget would be exceeded
- Budgets auto-reset at midnight
- Multi-tenant workspaces for teams
- Live HTML dashboard with per-agent and per-tool spend
- 24 pre-configured tool presets

Tech stack: Python, FastAPI, SQLite, Jinja2. One pip install, zero infrastructure dependencies.

It takes 30 seconds to start:

    pip install agent-gov-saas
    agent-gov start

Then register agents via curl/API and route their tool calls through the proxy. Dashboard at localhost:8000/dashboard.

Code: https://github.com/sschelliah2026-source/agent-gov
PyPI: https://pypi.org/project/agent-gov-saas/

Built over the last week as a side project. MIT licensed. 45 tests, 0.3s runtime. We'd love your feedback.
