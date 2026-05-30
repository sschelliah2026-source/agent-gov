# Inside agent-gov: Architecture of an Agent Cost Governance Platform

AI agents orchestrate complex workflows — calling LLMs, scraping pages, querying databases, sending emails. Each call costs real money. Without a governance layer, a single buggy loop can burn through your budget before anyone notices.

**agent-gov** is an open-source reverse proxy that intercepts every tool call your agents make, enforces budgets in real time, and auto-pauses out-of-control agents. We built it as a FastAPI service with SQLite persistence, and it runs 45 tests in 0.3 seconds.

This post walks through the architecture: the proxy pattern at its heart, the four-stage decision tree, cost tracking with a tool registry, multi-tenancy via workspaces, and the lazy auto-reset pattern that keeps daily budgets fresh without cron jobs.

---

## The Proxy Pattern

Every AI agent tool call passes through agent-gov before reaching the actual tool. The agent sends a `POST /proxy/call` with its API key, the tool name, and an optional estimated cost. agent-gov validates, budgets, and logs — then returns a 200 to approve or a 429 to reject.

```python
class ToolCall(BaseModel):
    agent_key: str = Field(...)
    tool_name: str = Field(...)
    estimated_cost: float = Field(0.0, ge=0)
```

The proxy doesn't execute the tool itself — it guards access. The agent only proceeds with the actual call if the proxy returns 200. This is the **gatekeeper pattern**: a lightweight decision layer between the agent and the outside world.

```
Agent ──POST /proxy/call──► agent-gov ──200/429──► Agent decides
                                                      │
                                                 Calls actual tool
                                                      │
                                                      ▼
                                               OpenAI / Browser / API
```

Why a proxy instead of a library? A library can be monkey-patched, removed, or forgotten. A proxy is a network boundary that agents *must* cross — it can't be bypassed by a rogue import or a version bump.

---

## The Decision Tree: Auth → Check → Budget → Log

Every proxy call runs through a four-stage pipeline. Each stage either passes to the next or terminates with a clear HTTP status code.

```python
@app.post("/proxy/call")
async def proxy_tool_call(call: ToolCall):
    key_hash = db.hash_key(call.agent_key)
    agent = await db.get_agent(key_hash)

    # Step 1: Auth
    if agent is None:
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Step 2: Paused check
    if agent["paused"]:
        raise HTTPException(status_code=429,
            detail=f"Agent '{agent['name']}' is paused.")

    # Step 3: Auto-reset budget if new day
    agent = await db.check_and_reset_budget(agent)

    # Step 4: Look up REAL tool cost
    registered_tool = await db.get_tool(call.tool_name)
    actual_cost = (registered_tool["cost_per_call"]
                   if registered_tool else call.estimated_cost)

    # Step 5: Budget check
    new_total = agent["spent_today"] + actual_cost
    if new_total > agent["daily_budget"]:
        await db.pause_agent(key_hash)
        raise HTTPException(status_code=429,
            detail="Budget exceeded — agent auto-paused.")

    # Step 6: Approved — update spend and log
    updated = await db.update_agent_spend(key_hash, actual_cost)
    await db.log_cost_event(key_hash, agent["name"], call.tool_name,
                            actual_cost)
    return {"status": "approved", ...}
```

The stages are:

| Stage | Check | Exit |
|---|---|---|
| **Auth** | Does the API key hash match a known agent? | 401 — Invalid key |
| **Pause** | Is the agent currently paused? | 429 — Agent paused |
| **Reset** | Has the calendar day changed since last call? | (silent reset if yes) |
| **Budget** | Would this call exceed the daily cap? | 429 — Budget exceeded + auto-pause |
| **Log** | INSERT cost event for analytics | 200 — Approved |

This linear pipeline is deliberately simple. There's no retry logic, no queue, no async approval. An agent tool call needs a yes/no in milliseconds, and HTTP status codes are the cleanest interface for that.

---

## Cost Tracking: Registry vs. Estimate

The trickiest design decision in agent-gov was how to determine a tool's cost. The naive approach — trust the agent's `estimated_cost` — is dangerously fragile. Agents can under-report (or forget to report) their spending. An agent claiming a GPT-4 call costs ₹0.01 while actually incurring ₹12.50 is a budget disaster waiting to happen.

agent-gov's solution is a **tool registry**: an UPSERT-able table of known tools with their real per-call costs.

```python
async def register_tool(name, cost_per_call, description,
                        workspace_id="default"):
    await db.execute("""
        INSERT INTO tools (name, cost_per_call, description,
                           registered_at, workspace_id)
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
actual_cost = (registered_tool["cost_per_call"]
               if registered_tool else call.estimated_cost)
```

If the tool is registered, its **true cost** is used — the agent's estimate is completely ignored. If the tool isn't in the registry (perhaps during early development), the estimate serves as a fallback. The response includes a `cost_source` field so clients know which path was taken:

```python
"cost_source": "registry" if registered_tool else "client_estimate"
```

This is verified by a test that proves an agent can't under-report its way past governance:

```python
async def test_proxy_uses_registered_cost_for_budget_check():
    # Register an expensive tool costing ₹500/call
    await c.post("/tools/register", json={
        "name": "expensive-model", "cost_per_call": 500.0
    })
    # Agent with ₹100 budget claims ₹1 estimate
    key = (await c.post("/agents/register", json={
        "name": "PoorBot", "daily_budget": 100
    })).json()["api_key"]
    r = await c.post("/proxy/call", json={
        "agent_key": key, "tool_name": "expensive-model",
        "estimated_cost": 1.0
    })
    # Blocked because real cost is ₹500 — way over budget
    assert r.status_code == 429
```

The test passes. The agent can't lie its way past the gate.

---

## Multi-Tenancy: Workspace Isolation

agent-gov v0.5 introduced workspaces — isolated tenants with their own agents, tools, and cost events. Each workspace gets a unique ID and API key. Every database row carries a `workspace_id` FK column.

The schema migration handles this gracefully using `PRAGMA table_info` — a technique that lets SQLite add columns only when they're missing:

```python
async def _add_col_if_missing(table, col_name, col_def):
    cursor = await db.execute(f"PRAGMA table_info({table})")
    existing = {row[1] for row in await cursor.fetchall()}
    if col_name not in existing:
        await db.execute(
            f"ALTER TABLE {table} ADD COLUMN {col_def}")

await _add_col_if_missing("agents", "workspace_id",
    "workspace_id TEXT REFERENCES workspaces(id)")
```

Why `PRAGMA table_info` over error-handling `ALTER TABLE`? Because SQLite doesn't support `IF NOT EXISTS` for `ALTER TABLE`. Checking the schema first is cleaner than catching exceptions at runtime.

All queries pass through workspace filters automatically:

```python
async def get_all_agents(workspace_id: str = None):
    if workspace_id:
        cursor = await db.execute(
            "SELECT * FROM agents WHERE workspace_id = ? "
            "ORDER BY paused DESC, spent_today DESC",
            (workspace_id,))
    else:
        cursor = await db.execute(
            "SELECT * FROM agents ORDER BY ...")
```

Workspace isolation is verified by a test that creates two workspaces, registers an agent in each, and confirms neither can see the other's agents or tools:

```python
async def test_workspace_isolation_agents():
    ws1 = (await c.post("/workspaces", json={
        "name": "Team A"})).json()["id"]
    ws2 = (await c.post("/workspaces", json={
        "name": "Team B"})).json()["id"]

    await c.post("/agents/register", json={
        "name": "BotA", "daily_budget": 100, "workspace_id": ws1})
    await c.post("/agents/register", json={
        "name": "BotB", "daily_budget": 200, "workspace_id": ws2})

    r = await c.get(f"/dashboard?workspace_id={ws1}")
    assert "BotA" in r.text
    assert "BotB" not in r.text  # Isolated!
```

A `default` workspace is auto-created for backward compatibility, and all NULL `workspace_id` values are migrated to it. This means existing installations upgrade to v0.5 without data loss.

---

## The Auto-Reset Pattern: Lazy Daily Budgets

Budget resets at midnight are a classic systems problem. A cron job that resets *every* agent at *exactly* midnight creates a thundering herd problem — hundreds of `UPDATE` queries hitting the database simultaneously.

agent-gov side-steps this entirely with **lazy evaluation**: instead of a scheduler that resets everyone at midnight, we check on every proxy call whether a reset is needed.

```python
async def check_and_reset_budget(agent: dict) -> dict:
    today = date.today().isoformat()

    # No reset needed if already on today's date
    if agent["last_reset"] == today:
        return agent

    # Don't auto-reset paused agents
    if agent["paused"]:
        return agent

    # Auto-reset: zero out counters, update date
    return await reset_daily_budget(agent["key_hash"])
```

The `last_reset` column stores the date of the most recent reset (ISO format: `2026-05-29`). The check is a string comparison on a single column — sub-millisecond overhead per call.

**Why this works:** an agent that makes no calls on a given day doesn't need a reset. An agent that makes its first call of the day gets a single `UPDATE` before the call is processed. The thundering herd becomes a gentle trickle spread across however many agents are actually active.

The test for this manually sets `last_reset` to a past date and confirms the next call resets counters transparently:

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

---

## What's Next

agent-gov's architecture — proxy gatekeeper, four-stage decision tree, tool registry with cost override, workspace-isolated multi-tenancy, and lazy budget resets — is intentionally minimal. Each feature solves a real problem without over-engineering.

The next evolution is already in view: per-tool budget caps (not just per-agent), webhook-based alerts when budgets are crossed, and a management API for programmatic policy updates. But the foundation — a simple, testable, async governance proxy — is solid.

*agent-gov is open source and MIT licensed. 45 tests. Zero database setup. One config file.*
