"""
agent-gov v0.5: AI Agent Cost Governance Platform
==================================================
NEW IN v0.6: Policy Engine — cost-aware governance policies (block tools, budget warnings, approvals).
- v0.5: Multi-tenancy — workspaces isolate teams, agents, tools, and costs.
- v0.4: Daily budget auto-reset — budgets reset at midnight automatically.
- v0.3: Per-tool cost tracking — real costs from tool registry, not client estimates.
- v0.2: SQLite persistence — data survives restarts.

A reverse proxy that sits between your agents and their tools.
Tracks costs, enforces budgets, auto-pauses overspending agents.

Run: cd agent-gov && source venv/bin/activate && python app.py
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from datetime import datetime, date
from contextlib import asynccontextmanager

# ──────────────────────────────────────────────
# LESSON 7: Database Layer Separation
# 
# All database logic is in database.py.
# app.py only calls high-level functions like:
#   db.create_agent(name, budget)
#   db.get_agent(key_hash)
# 
# This is called SEPARATION OF CONCERNS.
# - app.py knows about HTTP (routes, status codes)
# - database.py knows about storage (SQL, queries, migrations)
# 
# When you switch from SQLite to PostgreSQL later,
# you only change database.py — app.py stays the same.
# ──────────────────────────────────────────────

import database as db

# ──────────────────────────────────────────────
# LESSON 8: FastAPI Lifespan (Startup/Shutdown)
# 
# Instead of starting the DB connection at import time
# (which is unpredictable), we use FastAPI's lifespan system.
# 
# @asynccontextmanager wraps startup + shutdown in one block.
# Everything BEFORE yield runs at startup.
# Everything AFTER yield runs at shutdown.
# ──────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: connect to database. Shutdown: close connection."""
    await db.get_db()  # Initializes DB + creates tables
    print("✅ Database connected and schema ready")
    yield
    await db.close_db()
    print("✅ Database connection closed")

app = FastAPI(
    title="agent-gov",
    description="AI Agent Cost Governance Platform — with Policy Engine",
    version="0.6.0",
    lifespan=lifespan
)


# ──────────────────────────────────────────────
# MODELS (same as v0.1, no changes needed)
# The beauty of separation: models don't know
# if data goes to dict or SQLite.
# ──────────────────────────────────────────────

class ToolRegister(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    cost_per_call: float = Field(..., ge=0)
    description: str = Field("", max_length=500)
    workspace_id: str = Field("default", max_length=50)

class AgentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    daily_budget: float = Field(..., gt=0)
    workspace_id: str = Field("default", max_length=50)

class WorkspaceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field("", max_length=500)

class ToolCall(BaseModel):
    agent_key: str = Field(...)
    tool_name: str = Field(...)
    estimated_cost: float = Field(0.0, ge=0)


# ── v0.6: Policy Models ──

class PolicyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field("", max_length=500)
    policy_type: str = Field(...)
    policy_config: dict = Field(default_factory=dict)
    action: str = Field("block")
    workspace_id: str = Field("default", max_length=50)


class PolicyToggle(BaseModel):
    enabled: bool = Field(...)


# ── Approval Models ──

class ApprovalRequest(BaseModel):
    approval_id: str = Field(...)
    decision: str = Field(..., pattern="^(approve|deny)$")


# In-memory approval store (simple, non-persistent for MVP)
_pending_approvals: dict = {}


# ──────────────────────────────────────────────
# ROUTES (updated to use async database calls)
# ──────────────────────────────────────────────

@app.get("/")
async def root():
    """Health check + stats."""
    stats = await db.get_stats()
    return {
        "service": "agent-gov",
        "version": "0.5.1",
        "agents_registered": stats["agents_registered"],
        "total_calls_tracked": stats["total_calls_tracked"],
        "tools_registered": stats.get("tools_registered", 0),
        "docs": "/docs"
    }


@app.post("/agents/register")
async def register_agent(agent: AgentCreate):
    """Register a new agent in a workspace. Returns API key (one time only!).
    
    Workspace defaults to 'default' if not specified.
    """
    result = await db.create_agent(agent.name, agent.daily_budget, agent.workspace_id)
    return {
        "api_key": result["api_key"],
        "name": result["name"],
        "daily_budget": result["daily_budget"],
        "workspace_id": result.get("workspace_id", agent.workspace_id),
        "message": "Save this API key — it won't be shown again!"
    }


@app.post("/proxy/call")
async def proxy_tool_call(call: ToolCall):
    """Proxy a tool call through budget enforcement.
    
    v0.3: Now looks up the REAL tool cost from the tool registry.
    If the tool is registered, the registered cost is used.
    If not registered, falls back to the client's estimated_cost.
    This prevents agents from under-reporting costs.
    """
    key_hash = db.hash_key(call.agent_key)
    agent = await db.get_agent(key_hash)
    
    # Step 1: Auth
    if agent is None:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    # Step 2: Paused check
    if agent["paused"]:
        raise HTTPException(
            status_code=429,
            detail=f"Agent '{agent['name']}' is paused. Resume at /agents/{{key}}/resume"
        )
    
    # Step 3: Auto-reset budget if new day (v0.4)
    # Lazy evaluation: checks if last_reset != today
    # If so, silently resets spent_today and calls_today to 0
    agent = await db.check_and_reset_budget(agent)
    
    # Step 4: Look up REAL tool cost (v0.3 feature)
    # If tool is registered, use its real cost. Otherwise fall back to estimated.
    registered_tool = await db.get_tool(call.tool_name)
    actual_cost = registered_tool["cost_per_call"] if registered_tool else call.estimated_cost
    
    # Step 4b: Policy check (v0.6 feature)
    # Check all enabled policies before allowing the call.
    # Cost-aware policies can block tools that would be too expensive.
    workspace = agent.get("workspace_id", "default")
    policy_results = await db.check_policies(
        workspace_id=workspace,
        tool_name=call.tool_name,
        cost=actual_cost,
        spent_today=agent["spent_today"],
        daily_budget=agent["daily_budget"]
    )
    
    # Check for blocking policies
    blocking = [p for p in policy_results if p["action"] == "block"]
    if blocking:
        violations = [{"policy_id": p["policy_id"], "name": p["name"], "reason": p["reason"]} for p in blocking]
        raise HTTPException(
            status_code=403,
            detail={
                "error": "Policy violation",
                "violations": violations,
                "message": f"Blocked by {len(violations)} policy violation(s)"
            }
        )
    
    # Check for approval-required policies
    pending_approval = [p for p in policy_results if p["action"] == "require_approval"]
    approval_id = None
    if pending_approval:
        import uuid
        approval_id = "ap-" + uuid.uuid4().hex[:12]
        _pending_approvals[approval_id] = {
            "agent_key": call.agent_key,
            "tool_name": call.tool_name,
            "cost": actual_cost,
            "policies": [p["policy_id"] for p in pending_approval],
            "status": "pending",
            "created_at": datetime.now().isoformat()
        }
    
    # Step 4 (was 5): Budget check (using actual cost)
    new_total = agent["spent_today"] + actual_cost
    if new_total > agent["daily_budget"]:
        await db.pause_agent(key_hash)
        raise HTTPException(
            status_code=429,
            detail=(
                f"Budget would be exceeded. "
                f"Spent: ₹{agent['spent_today']:.2f}, "
                f"Budget: ₹{agent['daily_budget']:.2f}, "
                f"This call: ₹{actual_cost:.2f}. "
                f"Agent has been auto-paused."
            )
        )
    
    # Step 5: Approved — update spend and log
    updated = await db.update_agent_spend(key_hash, actual_cost)
    await db.log_cost_event(key_hash, agent["name"], call.tool_name, actual_cost)
    
    # Collect warnings from non-blocking policies
    warnings = [p["reason"] for p in policy_results if p["action"] == "warn"]
    
    response_data = {
        "status": "approved",
        "agent": agent["name"],
        "tool": call.tool_name,
        "estimated_cost": call.estimated_cost,
        "actual_cost": actual_cost,
        "cost_source": "registry" if registered_tool else "client_estimate",
        "spent_today": updated["spent_today"],
        "remaining": updated["daily_budget"] - updated["spent_today"],
        "calls_today": updated["calls_today"]
    }
    
    if approval_id:
        response_data["approval_id"] = approval_id
        response_data["approval_status"] = "pending"
        response_data["message"] = f"Tool call approved but requires confirmation. POST /approvals/{approval_id}/decide to confirm."
    
    if warnings:
        response_data["policy_warnings"] = warnings
    
    return response_data


@app.post("/agents/{api_key}/resume")
async def resume_agent(api_key: str):
    """Resume a paused agent."""
    key_hash = db.hash_key(api_key)
    agent = await db.get_agent(key_hash)
    
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    if not agent["paused"]:
        return {"status": "already_active", "name": agent["name"]}
    
    updated = await db.resume_agent(key_hash)
    return {
        "status": "resumed",
        "name": updated["name"],
        "daily_budget": updated["daily_budget"],
        "message": f"Agent resumed. Budget reset to ₹{updated['daily_budget']}/day."
    }


# ──────────────────────────────────────────────
# LESSON 10: Manual Budget Reset
# 
# Reset an agent's daily counters without changing pause status.
# Unlike resume (which unpauses), this only zeros out spend.
# Useful for: "start of day" calls from CI/CD, or admin corrections.
# ──────────────────────────────────────────────

@app.post("/agents/{api_key}/reset")
async def reset_agent_budget(api_key: str):
    """Reset an agent's daily spend counters to 0.
    
    Does NOT change pause status. For manual resets mid-day.
    Unlike /resume which also unpauses, this is a pure counter reset.
    """
    key_hash = db.hash_key(api_key)
    agent = await db.get_agent(key_hash)
    
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    updated = await db.reset_daily_budget(key_hash)
    was_paused = " (paused)" if agent["paused"] else ""
    return {
        "status": "reset",
        "name": updated["name"],
        "daily_budget": updated["daily_budget"],
        "spent_today": updated["spent_today"],
        "calls_today": updated["calls_today"],
        "message": f"Budget reset to ₹{updated['daily_budget']}/day for '{updated['name']}'{was_paused}."
    }


# ──────────────────────────────────────────────
# LESSON 9: Tool Registry Endpoints
# 
# Tools are registered with their known costs per call.
# The proxy then uses the REAL cost, not the agent's estimate.
# This prevents agents from under-reporting costs.
# ──────────────────────────────────────────────

@app.post("/tools/register")
async def register_tool(tool: ToolRegister):
    """Register a tool with its known cost per call, scoped to a workspace.
    
    If the tool already exists, updates its cost + description.
    Tools are identified by name (e.g., 'openai-gpt4', 'web-search').
    Workspace defaults to 'default' if not specified.
    """
    result = await db.register_tool(tool.name, tool.cost_per_call, tool.description, tool.workspace_id)
    return {
        "status": "registered" if tool.description else "updated",
        "tool": result
    }

@app.get("/tools")
async def list_tools(workspace_id: str = None):
    """List all registered tools, optionally filtered by workspace."""
    tools = await db.get_all_tools(workspace_id)
    if not tools:
        return {"tools": [], "message": "No tools registered yet. POST /tools/register to add one."}
    return {"tools": tools, "count": len(tools), "filter": {"workspace_id": workspace_id}}

@app.get("/analytics/tools")
async def tool_spend_analytics(workspace_id: str = None):
    """Get per-tool spend statistics, optionally filtered by workspace.
    
    Shows how much each tool has been called and total spend.
    """
    stats = await db.get_tool_spend_stats(workspace_id)
    return {
        "tools": stats,
        "total_tools": len(stats),
        "total_spend": sum(t["total_spent"] for t in stats),
        "filter": {"workspace_id": workspace_id}
    }


# ──────────────────────────────────────────────
# LESSON 11: Workspace API (Multi-Tenancy)
#
# Workspaces isolate teams/projects.
# Each workspace has its own agents, tools, and cost events.
# ──────────────────────────────────────────────

@app.post("/workspaces")
async def create_workspace(ws: WorkspaceCreate):
    """Create a new workspace. Returns workspace API key (one-time!)."""
    result = await db.create_workspace(ws.name, ws.description)
    return {
        "id": result["id"],
        "name": result["name"],
        "description": result["description"],
        "api_key": result["api_key"],
        "message": "Save this API key — it won't be shown again!"
    }

@app.get("/workspaces")
async def list_workspaces():
    """List all workspaces."""
    workspaces = await db.get_all_workspaces()
    if not workspaces:
        return {"workspaces": [], "message": "No workspaces yet. POST /workspaces to create one."}
    return {"workspaces": workspaces, "count": len(workspaces)}


# ═══════════════════════════════════════════════
# v0.6 — Policy Engine Endpoints
# ═══════════════════════════════════════════════

@app.get("/policies/types")
async def list_policy_types():
    """List all available policy types and their descriptions."""
    return {"policy_types": db.POLICY_TYPES, "actions": db.POLICY_ACTIONS}


@app.post("/policies")
async def create_policy(policy: PolicyCreate):
    """Create a new governance policy.
    
    Policy types:
    - block_tool: Deny a specific tool entirely. config: {"tool_name": "gpt-4"}
    - block_tool_over_cost: Deny if cost > threshold. config: {"max_cost": 5.0}
    - budget_warning: Warn at X% budget. config: {"threshold_pct": 80}
    - require_approval: Intercept for manual OK. config: {"tool_name": "deploy-api"}
    
    Actions: block, warn, require_approval
    """
    try:
        result = await db.create_policy(
            name=policy.name,
            policy_type=policy.policy_type,
            policy_config=policy.policy_config,
            action=policy.action,
            workspace_id=policy.workspace_id,
            description=policy.description
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/policies")
async def list_policies(workspace_id: str = None):
    """List all policies, optionally filtered by workspace."""
    policies = await db.list_policies(workspace_id)
    return {"policies": policies, "count": len(policies)}


@app.get("/policies/{policy_id}")
async def get_policy(policy_id: int):
    """Get a single policy by ID."""
    policy = await db.get_policy(policy_id)
    if policy is None:
        raise HTTPException(status_code=404, detail="Policy not found")
    return policy


@app.delete("/policies/{policy_id}")
async def delete_policy(policy_id: int):
    """Delete a policy by ID."""
    deleted = await db.delete_policy(policy_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Policy not found")
    return {"status": "deleted", "policy_id": policy_id}


@app.patch("/policies/{policy_id}/toggle")
async def toggle_policy(policy_id: int, toggle: PolicyToggle):
    """Enable or disable a policy."""
    policy = await db.toggle_policy(policy_id, toggle.enabled)
    if policy is None:
        raise HTTPException(status_code=404, detail="Policy not found")
    return policy


@app.post("/approvals/{approval_id}/decide")
async def decide_approval(approval_id: str, decision: ApprovalRequest):
    pending = _pending_approvals.get(approval_id)
    if pending is None:
        raise HTTPException(status_code=404, detail="Approval request not found")
    if pending["status"] != "pending":
        raise HTTPException(status_code=400, detail=f"Approval already {pending['status']}")
    
    if decision.decision == "approve":
        pending["status"] = "approved"
        return {
            "status": "approved",
            "tool_name": pending["tool_name"],
            "cost": pending["cost"],
            "message": "Tool call approved. The agent can proceed."
        }
    else:
        pending["status"] = "denied"
        return {
            "status": "denied",
            "tool_name": pending["tool_name"],
            "message": "Tool call denied by approver."
        }


@app.get("/approvals/pending")
async def list_pending_approvals():
    """List all pending approval requests."""
    pending = [
        {"approval_id": k, **v}
        for k, v in _pending_approvals.items()
        if v["status"] == "pending"
    ]
    return {"pending": pending, "count": len(pending)}


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(workspace_id: str = None):
    """Live dashboard showing agents + per-tool spend, filtered by workspace."""
    agents = await db.get_all_agents(workspace_id)
    stats = await db.get_stats(workspace_id)
    tool_stats = await db.get_tool_spend_stats(workspace_id)
    
    agents_list = []
    for agent in agents:
        remaining = agent["daily_budget"] - agent["spent_today"]
        pct = (agent["spent_today"] / agent["daily_budget"] * 100) if agent["daily_budget"] > 0 else 0
        
        if pct >= 100:
            bar_color = "#ef4444"
        elif pct >= 80:
            bar_color = "#f59e0b"
        else:
            bar_color = "#22c55e"
        
        agents_list.append({
            "name": agent["name"],
            "daily_budget": agent["daily_budget"],
            "spent_today": round(agent["spent_today"], 2),
            "remaining": round(remaining, 2),
            "calls_today": agent["calls_today"],
            "paused": agent["paused"],
            "pct": min(round(pct, 1), 100),
            "bar_color": bar_color,
            "last_reset": agent["last_reset"],
            "reset_today": agent["last_reset"] == date.today().isoformat()
        })
    
    agents_list.sort(key=lambda a: (not a["paused"], -a["pct"]))
    
    # Build tool breakdown HTML
    tool_rows = ""
    if tool_stats:
        max_spend = max(t["total_spent"] for t in tool_stats) or 1
        for t in tool_stats:
            tpct = (t["total_spent"] / max_spend * 100) if max_spend > 0 else 0
            tool_rows += f'''
            <div class="tool-row">
                <div class="tool-header">
                    <span class="tool-name">{t['tool_name']}</span>
                    <span class="tool-metrics">₹{t['total_spent']} · {t['total_calls']} calls · {t['agent_count']} agent(s)</span>
                </div>
                <div class="tool-bar"><div class="tool-fill" style="width:{tpct}%"></div></div>
            </div>'''
    else:
        tool_rows = '<div class="empty">No tool data yet. Register tools and make calls to see breakdown.</div>'
    
    # Build policies HTML (v0.6)
    policies = await db.list_policies(workspace_id)
    if policies:
        policy_rows = ""
        for p in policies:
            action_badge = ""
            if p["action"] == "block":
                action_badge = '<span class="badge badge-block">block</span>'
            elif p["action"] == "warn":
                action_badge = '<span class="badge badge-warn">warn</span>'
            elif p["action"] == "require_approval":
                action_badge = '<span class="badge badge-approval">approval</span>'
            enabled_badge = '<span class="badge badge-enabled">enabled</span>' if p["enabled"] else '<span class="badge badge-disabled">disabled</span>'
            viol = f' · {p["violation_count"]} violations' if p["violation_count"] > 0 else ''
            policy_rows += f'''
            <div class="policy-row">
                <div>
                    <div class="policy-name">{p["name"]}</div>
                    <div class="policy-detail">{p["policy_type"]} · {p.get("description", "")}{viol}</div>
                </div>
                <div>{action_badge} {enabled_badge}</div>
            </div>'''
        _policies_html = policy_rows
    else:
        _policies_html = '<div class="empty">No policies yet. POST /policies to create one.<br><br>Example: <code>curl -X POST /policies -d \'{"name":"Block GPT-4","policy_type":"block_tool","policy_config":{"tool_name":"gpt-4"},"action":"block"}\'</code></div>'
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>agent-gov — Cost Governance Dashboard</title>
    <style>
        *{{margin:0;padding:0;box-sizing:border-box}}
        body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0f172a;color:#e2e8f0;padding:24px}}
        .container{{max-width:800px;margin:0 auto}}
        h1{{font-size:1.5rem;margin-bottom:4px}}
        h2{{font-size:1.1rem;margin-bottom:16px;color:#94a3b8}}
        .subtitle{{color:#94a3b8;font-size:0.9rem;margin-bottom:32px}}
        .version{{background:#334155;padding:2px 8px;border-radius:4px;font-size:0.7rem;margin-left:8px}}
        .section{{margin-bottom:32px}}
        .stats{{display:flex;gap:16px;margin-bottom:32px}}
        .stat{{background:#1e293b;padding:16px;border-radius:8px;flex:1;text-align:center}}
        .stat .number{{font-size:1.5rem;font-weight:700}}
        .stat .label{{font-size:0.75rem;color:#94a3b8;margin-top:4px}}
        .agent-card{{background:#1e293b;border-radius:8px;padding:20px;margin-bottom:12px;border-left:4px solid #22c55e}}
        .agent-card.paused{{border-left-color:#ef4444;opacity:0.7}}
        .agent-card.warning{{border-left-color:#f59e0b}}
        .agent-header{{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px}}
        .agent-name{{font-weight:600;font-size:1.05rem}}
        .agent-status{{font-size:0.75rem;padding:3px 10px;border-radius:12px;font-weight:600}}
        .status-active{{background:#065f46;color:#6ee7b7}}
        .status-paused{{background:#7f1d1d;color:#fca5a5}}
        .status-warning{{background:#78350f;color:#fcd34d}}
        .progress-bar{{height:8px;background:#334155;border-radius:4px;margin-bottom:8px;overflow:hidden}}
        .progress-fill{{height:100%;border-radius:4px;transition:width 0.3s}}
        .agent-details{{display:flex;gap:24px;font-size:0.85rem;color:#94a3b8;flex-wrap:wrap}}
        .agent-details span strong{{color:#e2e8f0}}
        .tool-section{{background:#1e293b;border-radius:8px;padding:20px}}
        .tool-row{{margin-bottom:12px}}
        .tool-header{{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px}}
        .tool-name{{font-weight:600;font-size:0.95rem}}
        .tool-metrics{{font-size:0.8rem;color:#94a3b8}}
        .tool-bar{{height:6px;background:#334155;border-radius:3px;overflow:hidden}}
        .tool-fill{{height:100%;background:#818cf8;border-radius:3px;transition:width 0.3s}}
        .policy-section{{background:#1e293b;border-radius:8px;padding:20px;margin-bottom:12px}}
        .policy-row{{display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid #334155}}
        .policy-row:last-child{{border-bottom:none}}
        .policy-name{{font-weight:600;font-size:0.9rem}}
        .policy-detail{{font-size:0.8rem;color:#94a3b8}}
        .badge{{font-size:0.7rem;padding:2px 8px;border-radius:10px;font-weight:600}}
        .badge-block{{background:#7f1d1d;color:#fca5a5}}
        .badge-warn{{background:#78350f;color:#fcd34d}}
        .badge-approval{{background:#1e1b4b;color:#a5b4fc}}
        .badge-enabled{{background:#065f46;color:#6ee7b7}}
        .badge-disabled{{background:#334155;color:#94a3b8}}
        .empty{{text-align:center;color:#64748b;padding:40px 20px;font-size:0.9rem}}
        .refresh{{color:#94a3b8;font-size:0.8rem;text-align:right;margin-top:24px}}
        .persist{{background:#065f46;color:#6ee7b7;font-size:0.7rem;padding:2px 8px;border-radius:4px;margin-left:8px}}
        .v3-badge{{background:#4f46e5;color:#c7d2fe;font-size:0.7rem;padding:2px 8px;border-radius:4px;margin-left:4px}}
        .v6-badge{{background:#dc2626;color:#fca5a5;font-size:0.7rem;padding:2px 8px;border-radius:4px;margin-left:4px}}
        a{{color:#94a3b8}}
        .total-spend{{font-size:0.95rem;color:#c7d2fe;margin-bottom:12px}}
    </style>
    <meta http-equiv="refresh" content="10">
</head>
<body>
    <div class="container">
        <h1>🛡 agent-gov <span class="version">v0.6</span><span class="persist">💾 SQLite</span><span class="v3-badge">🏢 Multi-Tenant</span><span class="v6-badge">⚖️ Policy Engine</span></h1>
        <p class="subtitle">
            AI Agent Cost Governance — {'workspace: ' + workspace_id if workspace_id else 'all workspaces'}
        </p>
        
        <div class="stats">
            <div class="stat"><div class="number">{stats['agents_registered']}</div><div class="label">Agents</div></div>
            <div class="stat"><div class="number">{stats['total_calls_tracked']}</div><div class="label">Calls Tracked</div></div>
            <div class="stat"><div class="number">₹{sum(a['spent_today'] for a in agents):.2f}</div><div class="label">Today's Spend</div></div>
        </div>
        
        <div class="section">
        <h2>🤖 Agents</h2>
        {"".join(f'''
        <div class="agent-card {'paused' if a['paused'] else ('warning' if a['pct'] >= 80 else '')}">
            <div class="agent-header">
                <span class="agent-name">{a['name']}</span>
                <span class="agent-status {'status-paused' if a['paused'] else ('status-warning' if a['pct'] >= 80 else 'status-active')}">
                    {"⏸ PAUSED" if a['paused'] else ("⚠ "+str(a['pct'])+"%" if a['pct'] >= 80 else "✓ Active")}
                </span>
            </div>
            <div class="progress-bar"><div class="progress-fill" style="width:{a['pct']}%;background:{a['bar_color']}"></div></div>
            <div class="agent-details">
                <span>Budget: <strong>₹{a['daily_budget']}/day</strong></span>
                <span>Spent: <strong>₹{a['spent_today']}</strong></span>
                <span>Remaining: <strong>₹{a['remaining']}</strong></span>
                <span>Calls: <strong>{a['calls_today']}</strong></span>
                <span>Reset: <strong>{'✅ Today' if a['reset_today'] else ('📅 '+a['last_reset'])}</strong></span>
            </div>
        </div>
        ''' for a in agents_list) if agents_list else '<div class="empty">No agents yet.<br><br>POST /agents/register to create one.</div>'}
        </div>
        
        <div class="section">
        <h2>🔧 Spend by Tool</h2>
        <div class="tool-section">
            <div class="total-spend">Total tracked: ₹{sum(t['total_spent'] for t in tool_stats):.2f} across {len(tool_stats)} tool(s)</div>
            {tool_rows}
        </div>
        </div>
        
        <div class="section">
        <h2>⚖️ Policies</h2>
        {_policies_html}
        </div>
        
        <p class="refresh">Auto-refreshes 10s | <a href="/docs">API Docs →</a> | <a href="/tools">📋 Tools →</a> | <a href="/workspaces">🏢 Workspaces →</a> | <a href="/policies">⚖️ Policies →</a> | <a href="/policies/types">📖 Policy Types →</a></p>
    </div>
</body>
</html>"""
    return HTMLResponse(content=html)


# ──────────────────────────────────────────────
# RUN
# ──────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting agent-gov v0.6 (Policy Engine + Multi-Tenant + Auto-Reset + Tool Registry)")
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
