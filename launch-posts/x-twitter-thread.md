1/ We built agent-gov because an AI agent on our team burned ₹5,000 ($60) in GPT-4 credits in one night. 🔥

A recursive loop. Called itself. Generated more tokens. Called again. By morning the bill had tripled.

That was the day we realized AI agents need budget controls.

2/ So we built agent-gov — an open-source reverse proxy that sits between your agents and their tools.

Every tool call routes through the proxy. We check budgets, track per-tool costs, and auto-pause agents that overspend.

3/ Here's how it works in one diagram:

[MEDIA:/Users/maagzai/repos/agent-gov/launch-posts/architecture.png]

Agent → agent-gov proxy → 🔑 Auth → 💰 Budget check → ✅ Approved → Tool API
                                                   → 🛑 429 — Budget exceeded → Agent paused

4/ Features built so far:

• Per-agent daily budgets with auto-pause
• Tool registry with REAL costs (not agent estimates)
• Multi-tenant workspaces for teams
• Daily auto-reset at midnight
• Live dashboard with per-tool spend breakdown
• 24 pre-configured tool presets

5/ Tech stack: Python + FastAPI + SQLite + Jinja2

Install in 30 seconds:

    pip install agent-gov-saas
    agent-gov start

Dashboard at localhost:8000/dashboard. 45 tests, 0.3s runtime.

6/ Real dashboard in action:

[MEDIA:/Users/maagzai/repos/agent-gov/launch-posts/dashboard.png]

Register agents, route calls through the proxy, watch the spend in real-time. Auto-pause kicks in when budgets are exceeded.

7/ Everything is MIT licensed. GitHub + PyPI:

• https://github.com/sschelliah2026-source/agent-gov
• https://pypi.org/project/agent-gov-saas/

Built over a week. 45 tests, all passing. Feedback welcome! 🚀
