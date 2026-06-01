---
title: "The Receipt Your AI Didn't Know It Was Leaving"
published: true
description: "How agent-gov's observability layer gives you per-call visibility into every agent action — with an audit trail you can actually read."
tags: python, opensource, devops, observability
series: "Taming Your AI"
canonical_url: https://dev.to/maagzai/the-receipt-your-ai-didnt-know-it-was-leaving
---

## The Observability Gap

Most AI agent platforms are black boxes. You tell the agent what to do, it does it, you get the result — and you have no idea what happened in between.

Did it call 10 APIs or 100? Did it use the cheap model or the expensive one? Did it retry 50 times after hitting errors? Did it waste $300 on unnecessary computation?

With most systems, you'll never know.

agent-gov addresses this with a full **observability layer** — every single action is logged with: which agent, which tool, what it cost, whether it was approved or blocked, and when it happened.

## The Data Model

Every proxy call generates one row in the `cost_events` table:

```sql
CREATE TABLE cost_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_hash TEXT NOT NULL,
    agent_name TEXT NOT NULL,
    timestamp TEXT NOT NULL,        -- ISO 8601
    tool_name TEXT NOT NULL,        -- e.g., "openai-gpt4", "web-search"
    cost REAL NOT NULL,             -- exact cost in ₹
    FOREIGN KEY (agent_hash) REFERENCES agents(key_hash)
);
```

That's the atomic unit of observability. Every query you'd ever want can be built from this table:

```sql
-- Spend by agent today
SELECT agent_name, SUM(cost) as total, COUNT(*) as calls
FROM cost_events
WHERE date(timestamp) = date('now')
GROUP BY agent_name
ORDER BY total DESC;

-- Spend by tool this month
SELECT tool_name, SUM(cost) as total, COUNT(*) as calls
FROM cost_events
WHERE timestamp >= date('now', 'start of month')
GROUP BY tool_name
ORDER BY total DESC;

-- Anomaly detection: agents spending > 3x their daily average
SELECT agent_name, SUM(cost) as today_spend,
       (SELECT AVG(daily.cost) FROM (...)) as avg_daily
FROM cost_events
WHERE date(timestamp) = date('now')
GROUP BY agent_name
HAVING today_spend > avg_daily * 3;
```

## The Dashboard

The HTML dashboard (rendered server-side with Jinja2) shows:

- **Per-agent:** name, daily budget, spent today, calls today, paused status, budget bar
- **Per-tool:** total spend, call count, which agents use it, percentage bar
- **Aggregates:** total agents, total calls tracked, today's spend across all agents

Agents are sorted by paused status first (paused agents sink to bottom), then by spend percentage (highest first). Colors are traffic-light: green (< 80%), amber (80-99%), red (100%+ / paused).

## The Audit Trail

For compliance-heavy industries (healthcare, finance, legal), the audit trail is a hard requirement. Every action is logged with:

- **Who** — which agent (by name and key_hash)
- **What** — which tool was called
- **When** — ISO 8601 timestamp
- **How much** — exact cost in ₹
- **Result** — approved, blocked (with reason), or pending approval

```python
@app.post("/proxy/call")
async def proxy_tool_call(call: ToolCall):
    # ... auth, budget, policy checks ...

    # Log the event regardless of outcome
    await db.log_cost_event(
        key_hash=key_hash,
        agent_name=agent["name"],
        tool_name=call.tool_name,
        cost=actual_cost if approved else 0.0
    )
```

Every blocked call is also logged. This is critical for debugging: you can see *which* policies are triggering and *how often*.

## Quick Lookup

```bash
# Recent events
curl http://localhost:8000/analytics/tools
# Returns: { "tools": [{ "tool_name": "...", "total_spent": 123, ... }] }

# Dashboard
open http://localhost:8000/dashboard
```

## The Meta Point

The observability layer isn't just for debugging — it's the foundation for every other feature. The budget system reads from it. The policy engine writes to it. The dashboard renders it. The alerting system queries it.

Build the observability layer first. Everything else follows.

---

*This is part 5 of the "Taming Your AI" series. [agent-gov](https://github.com/sschelliah2026-source/agent-gov) is open-source, MIT-licensed, and logs every single agent action by default.*
