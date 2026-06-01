---
title: "Setting Ground Rules for Your Digital Employee"
published: true
description: "How cost-aware policies work in agent-gov — blocking expensive tools, warning at thresholds, and requiring approval for dangerous actions."
tags: python, opensource, security, devops
series: "Taming Your AI"
canonical_url: https://dev.to/maagzai/setting-ground-rules-for-your-digital-employee
---

## The Missing Layer in AI Safety

The AI safety conversation has focused on one question: **"Can the agent do this?"** (security — is this action dangerous, harmful, or against policy?)

agent-gov adds a second question that nobody else is asking: **"Can the agent AFFORD to do this?"** (cost — is this action worth it financially?)

Both questions matter. But cost-aware policies solve a different class of problem: agents wastefully using premium tools for routine tasks, burning budget on unnecessary computation, or escalating to expensive models when a cheaper alternative would work.

## How Policies Work

agent-gov's policy engine intercepts every proxy call and evaluates it against active rules. Each policy has:

- A **trigger condition** (when does this apply?)
- An **action** (what happens when triggered?)
- A **scope** (which agents or tools does it apply to?)

```python
# Core policy evaluation (simplified)
async def evaluate_policies(agent: dict, call: ToolCall, actual_cost: float) -> PolicyResult:
    policies = await db.get_active_policies(agent["workspace_id"])

    for policy in policies:
        if policy.matches(agent, call, actual_cost):
            if policy.action == "block":
                return PolicyResult.BLOCKED
            elif policy.action == "warn":
                await notify(agent, policy)
                # Continue — warning only
            elif policy.action == "approval":
                return PolicyResult.PENDING_APPROVAL

    return PolicyResult.APPROVED
```

## Real Policy Examples

### 1. Block Expensive Models

```
Condition: tool_name starts with "gpt-4" AND cost > $5.00
Action: BLOCK
Scope: all agents in workspace "production"
```

An agent trying to use GPT-4 for routine tasks gets stopped. The call returns a 429 with a clear reason: "Tool blocked by policy: cost exceeds $5.00 threshold."

### 2. Budget Warnings

```
Condition: agent.spent_today / agent.daily_budget >= 0.80
Action: WARN (notify workspace admin)
Scope: all agents
```

The agent keeps running, but the team gets notified. 80% warning, 90% repeat warning, 100% auto-pause.

### 3. Approval Gates

```
Condition: tool_name == "data-export" OR tool_name == "deploy"
Action: REQUIRE_APPROVAL
Scope: all agents
```

The agent pauses mid-task and waits for a human to approve. The approval request includes: which agent, which tool, estimated cost, and context.

## Why Cost-Aware Policies Are Different

Most AI policy engines treat all policy violations as security incidents. They can't distinguish between:

- "Agent called an unknown API" (security — block)
- "Agent used GPT-4 to summarize a 2-line email" (wasteful — redirect, don't block)
- "Agent wants to export customer data" (sensitive — require approval)

agent-gov's policies are cost-aware by default. The same policy engine that blocks a $15 premium API call can also warn at 80% budget usage or require approval for expensive actions. The trigger is cost, not just capability.

## Tested Behavior

```python
async def test_policy_blocks_expensive_tool():
    # Register a policy: block tools over $5
    await c.post("/policies", json={
        "name": "block-premium",
        "condition": "tool.actual_cost > 5.00",
        "action": "block",
        "workspace_id": "default"
    })
    # Agent tries a $12 tool
    key = (await c.post("/agents/register", json={
        "name": "TestBot", "daily_budget": 100
    })).json()["api_key"]
    await c.post("/tools/register", json={
        "name": "premium-api", "cost_per_call": 12.00
    })
    r = await c.post("/proxy/call", json={
        "agent_key": key, "tool_name": "premium-api",
        "estimated_cost": 12.00
    })
    assert r.status_code == 429
    assert "blocked" in r.json()["detail"]
```

## The Practical Impact

Without cost-aware policies, a clinic AI assistant trying to read a patient ID would default to a premium OCR API costing $12/call. With a simple policy ("max $5 per tool call"), the proxy blocks it and the agent falls back to the standard OCR at $0.80. No human intervention required.

The agent still completes its task. It just does it cost-effectively.

---

*This is part 4 of the "Taming Your AI" series. [agent-gov](https://github.com/sschelliah2026-source/agent-gov) has cost-aware policies built in — try it with `pip install agent-gov-saas`.*
