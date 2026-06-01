---
title: "Giving Your Digital Employee a Company Credit Card (With Limits)"
published: false
description: "How agent-gov implements daily budgets, real cost tracking, and lazy auto-reset — the engineering behind AI spending limits."
tags: python, opensource, finops, devops
series: "Taming Your AI"
canonical_url: https://dev.to/maagzai/giving-your-digital-employee-a-company-credit-card-with-limits
---

## The Core Problem

When you give a human employee a company credit card, you set a limit and review receipts. Most companies give their AI agents API keys — the digital equivalent of an unlimited card — and hope for the best.

Here's how the $30K bill actually plays out in practice:

```
Day 1:    Agent runs 50 tasks, costs $12. Looks great.
Day 5:    Agent discovers a premium model, uses it for everything. $80/day.
Day 10:   Agent runs 200 tasks/day (it's being helpful!). $400/day.
Day 20:   Agent enters a loop: calls expensive tools, gets results, calls again. $2,000/day.
Day 30:   You check your bill. $30,000.
```

The agent didn't do anything wrong. It just kept being "helpful."

## The Budget Engine: Daily Caps with Auto-Reset

agent-gov implements per-agent daily budgets through SQLite persistence with lazy evaluation:

```python
async def check_and_reset_budget(agent: dict) -> dict:
    today = date.today().isoformat()

    # No reset needed if already on today's date
    if agent["last_reset"] == today:
        return agent

    # Don't auto-reset paused agents — they need manual resume
    if agent["paused"]:
        return agent

    # Auto-reset: zero out counters, update date
    return await reset_daily_budget(agent["key_hash"])
```

The `last_reset` column stores an ISO date string. The check is a string comparison — sub-millisecond overhead per call.

**Why lazy evaluation instead of a cron job?** A midnight cron resetting *every* agent simultaneously creates a thundering herd of UPDATE queries. With lazy evaluation, an agent that makes no calls doesn't need a reset. The first call of the day triggers a single UPDATE. The herd becomes a trickle.

Test verifying the pattern:

```python
async def test_auto_reset_on_new_day():
    # ... register agent, spend ₹100 ...
    # Manually set last_reset to yesterday
    db.execute("UPDATE agents SET last_reset='2000-01-01', "
               "spent_today=100, calls_today=1 WHERE key_hash=?",
               (key_hash,))
    # Next proxy call auto-resets, then deducts
    r = await c.post("/proxy/call", json={
        "agent_key": key, "tool_name": "y", "estimated_cost": 30})
    assert r.json()["spent_today"] == 30  # Reset to 0, then +30
    assert r.json()["calls_today"] == 1
```

Counter resets to 0 transparently before the new call is charged.

## The Real Cost Problem

Here's the trick agents play (unintentionally, but still):

An agent says: "I need to call the premium research API. Estimated cost: $0.50."

The truth: that API costs $15.00/call.

agent-gov maintains a **tool registry** — a SQLite table of known tools with their real costs:

```python
async def register_tool(name, cost_per_call, description, workspace_id="default"):
    await db.execute("""
        INSERT INTO tools (name, cost_per_call, description, registered_at, workspace_id)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(name) DO UPDATE SET
            cost_per_call = excluded.cost_per_call,
            description = excluded.description,
            registered_at = excluded.registered_at,
            workspace_id = excluded.workspace_id
    """, (name, cost_per_call, description, now, workspace_id))
```

When a proxy call arrives, the pipeline does a two-step lookup:

```python
registered_tool = await db.get_tool(call.tool_name)
actual_cost = registered_tool["cost_per_call"] \
              if registered_tool else call.estimated_cost
```

If the tool is registered, its **true cost** is used — the agent's estimate is completely ignored.

## Beyond Per-Agent: Budget Pools

For teams running multiple agents, per-agent budgets aren't enough. You need shared pools with individual caps:

```
agent-gov pool create production-agents --budget 1000
agent-gov pool member add web-research-agent --pool production-agents --max-per-agent 200
```

Now the web agent is capped at $200/month even though the pool has $1,000. It can't starve the other agents.

## The Data Model

The entire budget system is two SQLite tables:

```sql
CREATE TABLE agents (
    key_hash TEXT PRIMARY KEY,        -- SHA-256 of API key
    name TEXT NOT NULL,
    daily_budget REAL NOT NULL,
    spent_today REAL NOT NULL DEFAULT 0.0,
    calls_today INTEGER NOT NULL DEFAULT 0,
    paused INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    last_reset TEXT NOT NULL           -- ISO date of last reset
);

CREATE TABLE cost_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_hash TEXT NOT NULL,
    agent_name TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    cost REAL NOT NULL,
    FOREIGN KEY (agent_hash) REFERENCES agents(key_hash)
);
```

That's it. Two tables, two queries per proxy call, sub-millisecond overhead.

## What This Means

| Before agent-gov | After agent-gov |
|---|---|
| "I wonder what our AI costs" | "I know exactly: $127.43 today" |
| "Can agents run wild?" | "Each agent has a hard daily limit" |
| "What if costs spike?" | "Agent auto-pauses. Alert sent." |

The budget isn't about restricting your AI — it's about freedom within boundaries. Like a good parent who says "play anywhere in the backyard, but don't climb the fence."

---

*This is part 3 of the "Taming Your AI" series. [agent-gov](https://github.com/sschelliah2026-source/agent-gov) is open-source, MIT-licensed. 45 tests, zero database setup.*
