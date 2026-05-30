# Announcing agent-gov: Open-Source AI Agent Cost Governance

**Stop waking up to surprise $500 bills from your AI agents.**

---

## The 3 AM Wake-Up Call

It was 3:47 AM on a Tuesday. My phone buzzed — a Cloudflare bill alert. Then another. Then Stripe. By the time I stumbled to my laptop, three different providers had collectively racked up **$487** in just six hours.

What happened? A single AI coding agent had gotten stuck in a loop. It was re-analyzing the same bug, calling the same expensive LLM endpoint over and over, spawning sub-agents that spawned *their own* sub-agents. Nobody put a governor on it. Nobody thought they needed to.

If you've built anything with AI agents — auto-pR reviewers, customer-support bots, code-gen pipelines, web-research assistants — you've either had this nightmare or you're one sleep cycle away from it. The fundamental problem is simple: **agents spend money the same way junior devs write code — enthusiastically, autonomously, and without asking permission.**

Most teams solve this with spreadsheets and hope. Some bolt on a cloud budget alert *after* the first blowup. A few give up on agents entirely.

We wanted a real answer.

## Enter agent-gov

Today I'm releasing **agent-gov** — an open-source, MIT-licensed cost governance platform purpose-built for AI agents. It's a lightweight reverse proxy that sits *between* your agents and their LLM providers, tracking every cent, enforcing daily budgets, and **auto-pausing agents that overspend.**

```
pip install agent-gov-saas
agent-gov start
```

That's it. Thirty seconds from zero to governance.

## How It Works

Agent-gov is transparent to your agents. You point them at a local proxy endpoint instead of directly at the API, and agent-gov handles the rest:

1. **Intercept** — every model call routes through agent-gov's FastAPI proxy
2. **Look up real costs** — the built-in tool registry knows exact per-token pricing for hundreds of models across OpenAI, Anthropic, Google, Mistral, DeepSeek, and more
3. **Enforce budgets** — if an agent exceeds its daily allocation, agent-gov returns an informative policy-blocked response instead of letting the call through
4. **Persist everything** — all usage is written to a local SQLite database via aiosqlite, so nothing is lost on restart

No lock-in. No cloud dependency. No per-seat licensing. Just a Python process that says "no" on your behalf.

## Features in v0.5

The initial release punches well above its weight:

- **Reverse proxy middleware** — drop-in for any OpenAI-compatible client
- **SQLite persistence** — full audit trail of every call, token, and dollar
- **Tool registry with real cost tables** — priced by model, provider, and input/output token rates
- **Daily budgets with auto-reset** — configure per-agent, per-workspace, or globally
- **Auto-pause on over-budget** — agents get a structured policy block, not a silent drain
- **Multi-tenant workspaces** — isolate costs by team, project, or environment
- **Docker support** — `docker compose up` for containerized deployments
- **45 tests, 0.3 seconds** — a tight, fast, well-tested codebase

## Quickstart

```bash
# Install
pip install agent-gov-saas

# Start the proxy (defaults to port 8080)
agent-gov start

# In another terminal, point your agent at it
# Instead of: openai.base_url = "https://api.openai.com/v1"
# Use:        openai.base_url = "http://localhost:8080/v1"
```

Want to set a daily budget of $5 for your code-review agent?

```bash
agent-gov config set budget 5.00 --agent code-review-bot
```

That's the whole workflow. Agent-gov handles the rest — tracking, enforcement, reset at midnight.

Prefer Docker?

```bash
docker run -p 8080:8080 ghcr.io/agent-gov/agent-gov:latest
```

## Why We Built This

The AI agent ecosystem is exploding — and rightfully so. Agents are genuinely useful. But the operational maturity around them is where web apps were in 2009 (remember "deploy by FTP"?). We're all running agents without guardrails because nobody has built the guardrails yet.

Agent-gov is our attempt to fix that. It's the **circuit breaker** for your agent infrastructure — the thing that prevents a single runaway loop from costing you a week of GPU credits or a surprise AWS bill.

The project is MIT-licensed because cost governance isn't a moat — it's table stakes. Every team running agents should have this, not just teams with a vendor budget.

## What's Next

v0.5 is just the beginning. The immediate roadmap includes:

- **Slack/email/webhook alerts** — "Your agent hit 80% of daily budget"
- **Per-endpoint budgeting** — cap tool calls, not just dollar amounts
- **Usage dashboards** — a simple web UI for visualizing spend per agent, per workspace
- **Anthropic/Google proxy support** — beyond OpenAI-compatible
- **Config-as-code** — YAML-based policies you can version-control

But we're not building this in a vacuum. The whole point of open-source is that the people who live this problem every day shape the solution.

## Get Involved

- **GitHub:** [github.com/agent-gov/agent-gov](https://github.com/agent-gov/agent-gov) — star, fork, open issues
- **Install:** `pip install agent-gov-saas`
- **Docs:** Read the README — it covers configuration, workspaces, budget policies, and API
- **Contributions:** PRs welcome. We need better provider coverage, dashboard UIs, deployment guides
- **Discussions:** We're tracking the 2025 agent-cost landscape — share your horror stories and wishlist features

The agent ecosystem is growing faster than any of us can keep up with. Let's make sure the infrastructure keeps pace.

**Don't learn you need cost governance at 3 AM.**

---

*agent-gov is an open-source project released under the MIT License. Built with FastAPI, SQLite, and a healthy fear of surprise bills.*

*— The agent-gov team*
