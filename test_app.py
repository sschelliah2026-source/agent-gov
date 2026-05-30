"""
Tests for agent-gov v0.2 — SQLite Persistence

Run: cd agent-gov && source venv/bin/activate && python -m pytest test_app.py -v
"""

import pytest
import os
import tempfile

# Fresh temp DB for this test run — deleted after tests
TEST_DB = os.path.join(tempfile.gettempdir(), f"agent-gov-test-{os.getpid()}.db")
os.environ["AGENT_GOV_TEST_DB"] = TEST_DB

from app import app
from httpx import AsyncClient, ASGITransport

pytestmark = pytest.mark.asyncio

# Simple async client helper
async def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


# --- Registration ---

async def test_register_returns_api_key():
    async with await client() as c:
        r = await c.post("/agents/register", json={"name": "Bot", "daily_budget": 500})
        assert r.status_code == 200
        assert r.json()["api_key"].startswith("ag-")

async def test_register_empty_name_fails():
    async with await client() as c:
        r = await c.post("/agents/register", json={"name": "", "daily_budget": 500})
        assert r.status_code == 422

async def test_register_negative_budget_fails():
    async with await client() as c:
        r = await c.post("/agents/register", json={"name": "Bot", "daily_budget": -100})
        assert r.status_code == 422

async def test_unique_keys():
    async with await client() as c:
        r1 = await c.post("/agents/register", json={"name": "A", "daily_budget": 100})
        r2 = await c.post("/agents/register", json={"name": "B", "daily_budget": 200})
        assert r1.json()["api_key"] != r2.json()["api_key"]


# --- Proxy ---

async def _register(c, budget=500):
    r = await c.post("/agents/register", json={"name": "Bot", "daily_budget": budget})
    return r.json()["api_key"]

async def test_proxy_approves_call():
    async with await client() as c:
        key = await _register(c)
        r = await c.post("/proxy/call", json={"agent_key": key, "tool_name": "fc", "estimated_cost": 50})
        assert r.status_code == 200
        assert r.json()["spent_today"] == 50

async def test_proxy_multiple_calls():
    async with await client() as c:
        key = await _register(c)
        await c.post("/proxy/call", json={"agent_key": key, "tool_name": "a", "estimated_cost": 100})
        r = await c.post("/proxy/call", json={"agent_key": key, "tool_name": "b", "estimated_cost": 200})
        assert r.json()["spent_today"] == 300

async def test_proxy_invalid_key():
    async with await client() as c:
        r = await c.post("/proxy/call", json={"agent_key": "ag-bad", "tool_name": "x", "estimated_cost": 10})
        assert r.status_code == 401

async def test_proxy_blocks_exceeded():
    async with await client() as c:
        key = await _register(c, budget=100)
        await c.post("/proxy/call", json={"agent_key": key, "tool_name": "a", "estimated_cost": 90})
        r = await c.post("/proxy/call", json={"agent_key": key, "tool_name": "b", "estimated_cost": 20})
        assert r.status_code == 429

async def test_proxy_auto_pauses():
    async with await client() as c:
        key = await _register(c, budget=100)
        await c.post("/proxy/call", json={"agent_key": key, "tool_name": "a", "estimated_cost": 90})
        await c.post("/proxy/call", json={"agent_key": key, "tool_name": "b", "estimated_cost": 20})
        r = await c.post("/proxy/call", json={"agent_key": key, "tool_name": "c", "estimated_cost": 5})
        assert r.status_code == 429

async def test_proxy_zero_cost():
    async with await client() as c:
        key = await _register(c, budget=100)
        r = await c.post("/proxy/call", json={"agent_key": key, "tool_name": "f", "estimated_cost": 0})
        assert r.status_code == 200

async def test_proxy_exact_budget():
    async with await client() as c:
        key = await _register(c, budget=100)
        await c.post("/proxy/call", json={"agent_key": key, "tool_name": "a", "estimated_cost": 99})
        r = await c.post("/proxy/call", json={"agent_key": key, "tool_name": "b", "estimated_cost": 1})
        assert r.status_code == 200


# --- Resume ---

async def test_resume_paused():
    async with await client() as c:
        key = await _register(c, budget=100)
        await c.post("/proxy/call", json={"agent_key": key, "tool_name": "a", "estimated_cost": 95})
        await c.post("/proxy/call", json={"agent_key": key, "tool_name": "b", "estimated_cost": 10})
        r = await c.post(f"/agents/{key}/resume")
        assert r.json()["status"] == "resumed"

async def test_resume_already_active():
    async with await client() as c:
        key = await _register(c, budget=100)
        r = await c.post(f"/agents/{key}/resume")
        assert r.json()["status"] == "already_active"

async def test_resume_not_found():
    async with await client() as c:
        r = await c.post("/agents/ag-fake123/resume")
        assert r.status_code == 404


# --- Dashboard ---

async def test_dashboard_html():
    async with await client() as c:
        r = await c.get("/dashboard")
        assert r.status_code == 200
        assert "agent-gov" in r.text

async def test_dashboard_with_agents():
    async with await client() as c:
        await c.post("/agents/register", json={"name": "DashBot", "daily_budget": 500})
        r = await c.get("/dashboard")
        assert "DashBot" in r.text


# --- Health ---

async def test_root():
    async with await client() as c:
        r = await c.get("/")
        assert r.json()["service"] == "agent-gov"

async def test_root_counts():
    async with await client() as c:
        before = (await c.get("/")).json()["agents_registered"]
        await c.post("/agents/register", json={"name": "A", "daily_budget": 100})
        await c.post("/agents/register", json={"name": "B", "daily_budget": 200})
        r = await c.get("/")
        assert r.json()["agents_registered"] == before + 2


# --- Edge Cases ---

async def test_large_budget():
    async with await client() as c:
        key = await _register(c, budget=1_000_000)
        r = await c.post("/proxy/call", json={"agent_key": key, "tool_name": "big", "estimated_cost": 500_000})
        assert r.status_code == 200

async def test_micro_budget():
    async with await client() as c:
        key = await _register(c, budget=0.01)
        r1 = await c.post("/proxy/call", json={"agent_key": key, "tool_name": "t", "estimated_cost": 0.01})
        assert r1.status_code == 200
        r2 = await c.post("/proxy/call", json={"agent_key": key, "tool_name": "t", "estimated_cost": 0.01})
        assert r2.status_code == 429


# --- Persistence ---

async def test_spend_accumulates():
    async with await client() as c:
        key = await _register(c, budget=200)
        await c.post("/proxy/call", json={"agent_key": key, "tool_name": "a", "estimated_cost": 50})
        r = await c.post("/proxy/call", json={"agent_key": key, "tool_name": "b", "estimated_cost": 30})
        assert r.json()["spent_today"] == 80

async def test_data_survives_multiple_requests():
    async with await client() as c:
        before = (await c.get("/")).json()["agents_registered"]
        for i in range(3):
            await c.post("/agents/register", json={"name": f"Bot{i}", "daily_budget": 100})
        r = await c.get("/")
        assert r.json()["agents_registered"] == before + 3


# ═══════════════════════════════════════════════
# v0.3 — Tool Registry + Real Cost Tracking
# ═══════════════════════════════════════════════

async def test_register_tool():
    async with await client() as c:
        r = await c.post("/tools/register", json={
            "name": "deepseek-chat",
            "cost_per_call": 0.15,
            "description": "DeepSeek Chat API call"
        })
        assert r.status_code == 200
        assert r.json()["tool"]["name"] == "deepseek-chat"
        assert r.json()["tool"]["cost_per_call"] == 0.15

async def test_register_tool_empty_name_fails():
    async with await client() as c:
        r = await c.post("/tools/register", json={
            "name": "",
            "cost_per_call": 0.15
        })
        assert r.status_code == 422

async def test_register_tool_negative_cost_fails():
    async with await client() as c:
        r = await c.post("/tools/register", json={
            "name": "bad-tool",
            "cost_per_call": -1
        })
        assert r.status_code == 422

async def test_update_existing_tool():
    async with await client() as c:
        # Register first
        await c.post("/tools/register", json={
            "name": "dynamic-tool",
            "cost_per_call": 1.0,
            "description": "Old price"
        })
        # Update
        r = await c.post("/tools/register", json={
            "name": "dynamic-tool",
            "cost_per_call": 2.5,
            "description": "New price"
        })
        assert r.status_code == 200
        assert r.json()["tool"]["cost_per_call"] == 2.5

async def test_list_tools():
    async with await client() as c:
        await c.post("/tools/register", json={
            "name": "test-tool-a",
            "cost_per_call": 0.10
        })
        await c.post("/tools/register", json={
            "name": "test-tool-b",
            "cost_per_call": 0.20
        })
        r = await c.get("/tools")
        assert r.status_code == 200
        names = [t["name"] for t in r.json()["tools"]]
        assert "test-tool-a" in names
        assert "test-tool-b" in names

async def test_proxy_uses_registered_tool_cost():
    """Proxy should use the registered tool cost, not the client's estimate."""
    async with await client() as c:
        # Register a tool with known cost
        await c.post("/tools/register", json={
            "name": "premium-llm",
            "cost_per_call": 10.0
        })
        # Register agent with budget
        key = (await c.post("/agents/register", json={"name": "CostBot", "daily_budget": 100})).json()["api_key"]
        # Call with estimated_cost=1.0, but tool costs 10.0
        r = await c.post("/proxy/call", json={
            "agent_key": key, "tool_name": "premium-llm", "estimated_cost": 1.0
        })
        assert r.status_code == 200
        # Should use actual cost of 10.0, not the estimate of 1.0
        assert r.json()["actual_cost"] == 10.0
        assert r.json()["cost_source"] == "registry"
        assert r.json()["spent_today"] == 10.0

async def test_proxy_falls_back_to_estimate():
    """Proxy should fall back to estimated_cost when tool is NOT registered."""
    async with await client() as c:
        key = (await c.post("/agents/register", json={"name": "EstBot", "daily_budget": 100})).json()["api_key"]
        r = await c.post("/proxy/call", json={
            "agent_key": key, "tool_name": "unregistered-tool", "estimated_cost": 5.0
        })
        assert r.status_code == 200
        assert r.json()["actual_cost"] == 5.0
        assert r.json()["cost_source"] == "client_estimate"

async def test_proxy_uses_registered_cost_for_budget_check():
    """Budget enforcement should use registered cost, blocking expensive tools."""
    async with await client() as c:
        # Register an expensive tool
        await c.post("/tools/register", json={
            "name": "expensive-model",
            "cost_per_call": 500.0
        })
        # Agent with small budget claims cheap estimate
        key = (await c.post("/agents/register", json={"name": "PoorBot", "daily_budget": 100})).json()["api_key"]
        r = await c.post("/proxy/call", json={
            "agent_key": key, "tool_name": "expensive-model", "estimated_cost": 1.0
        })
        # Should be blocked because real cost is 500 (way over 100 budget)
        assert r.status_code == 429

async def test_analytics_tools():
    async with await client() as c:
        # Register tools
        await c.post("/tools/register", json={"name": "analytics-tool", "cost_per_call": 2.0})
        # Register agent and make calls
        key = (await c.post("/agents/register", json={"name": "AnalyticsBot", "daily_budget": 100})).json()["api_key"]
        await c.post("/proxy/call", json={"agent_key": key, "tool_name": "analytics-tool", "estimated_cost": 0})
        
        r = await c.get("/analytics/tools")
        assert r.status_code == 200
        tools = r.json()["tools"]
        assert len(tools) > 0
        # Find our analytics-tool
        analytics = [t for t in tools if t["tool_name"] == "analytics-tool"]
        assert len(analytics) == 1
        assert analytics[0]["total_calls"] >= 1
        assert analytics[0]["total_spent"] >= 2.0

async def test_dashboard_shows_tool_section():
    async with await client() as c:
        r = await c.get("/dashboard")
        assert r.status_code == 200
        assert "Spend by Tool" in r.text
        assert "Multi-Tenant" in r.text or "Workspaces" in r.text

async def test_root_shows_tools_count():
    async with await client() as c:
        await c.post("/tools/register", json={"name": "count-test", "cost_per_call": 1.0})
        r = await c.get("/")
        assert r.json()["version"] == "0.5.1"
        assert "tools_registered" in r.json()


# ═══════════════════════════════════════════════
# v0.4 — Daily Budget Auto-Reset
# ═══════════════════════════════════════════════

async def test_manual_reset_zeros_counters():
    """Reset endpoint should zero out spent_today and calls_today."""
    async with await client() as c:
        key = (await c.post("/agents/register", json={"name": "ResetBot", "daily_budget": 500})).json()["api_key"]
        # Spend some budget
        await c.post("/proxy/call", json={"agent_key": key, "tool_name": "a", "estimated_cost": 100})
        await c.post("/proxy/call", json={"agent_key": key, "tool_name": "b", "estimated_cost": 50})
        # Verify spent
        r = await c.get("/")
        # Reset
        r = await c.post(f"/agents/{key}/reset")
        assert r.status_code == 200
        assert r.json()["spent_today"] == 0
        assert r.json()["calls_today"] == 0
        assert r.json()["daily_budget"] == 500

async def test_manual_reset_keeps_paused_status():
    """Reset should NOT change pause status."""
    async with await client() as c:
        key = (await c.post("/agents/register", json={"name": "PausedReset", "daily_budget": 50})).json()["api_key"]
        # Exceed budget to get paused
        await c.post("/proxy/call", json={"agent_key": key, "tool_name": "a", "estimated_cost": 100})
        r = await c.post(f"/agents/{key}/reset")
        assert r.status_code == 200
        assert "paused" in r.json()["message"]

async def test_reset_not_found():
    """Reset with invalid key should return 404."""
    async with await client() as c:
        r = await c.post("/agents/ag-invalid123/reset")
        assert r.status_code == 404

async def test_auto_reset_on_new_day():
    """Proxy call should auto-reset when last_reset is from a past day."""
    import aiosqlite
    import os
    import tempfile
    
    # Use the same temp DB setup as the test file
    test_db = os.path.join(tempfile.gettempdir(), f"agent-gov-test-{os.getpid()}.db")
    
    async with await client() as c:
        key = (await c.post("/agents/register", json={"name": "DayBot", "daily_budget": 500})).json()["api_key"]
        # Make a call today
        await c.post("/proxy/call", json={"agent_key": key, "tool_name": "x", "estimated_cost": 100})
        
        # Manually set last_reset to yesterday to simulate crossing midnight
        key_hash = __import__("hashlib").sha256(key.encode()).hexdigest()
        async with aiosqlite.connect(test_db) as db:
            await db.execute("UPDATE agents SET last_reset = '2000-01-01', spent_today = 100, calls_today = 1 WHERE key_hash = ?", (key_hash,))
            await db.commit()
        
        # Make another call — should auto-reset then deduct
        r = await c.post("/proxy/call", json={"agent_key": key, "tool_name": "y", "estimated_cost": 30})
        assert r.status_code == 200
        # After auto-reset to 0, 30 was spent
        assert r.json()["spent_today"] == 30
        assert r.json()["calls_today"] == 1

async def test_auto_reset_does_not_affect_current_day():
    """Proxy call should NOT reset if last_reset is already today."""
    async with await client() as c:
        key = (await c.post("/agents/register", json={"name": "SameDayBot", "daily_budget": 500})).json()["api_key"]
        await c.post("/proxy/call", json={"agent_key": key, "tool_name": "a", "estimated_cost": 50})
        r = await c.post("/proxy/call", json={"agent_key": key, "tool_name": "b", "estimated_cost": 30})
        assert r.status_code == 200
        assert r.json()["spent_today"] == 80  # Accumulated, not reset

async def test_dashboard_shows_reset_info():
    """Dashboard should show reset status per agent."""
    async with await client() as c:
        r = await c.get("/dashboard")
        assert r.status_code == 200
        assert "Reset:" in r.text or "Today" in r.text


# ═══════════════════════════════════════════════
# v0.5 — Multi-Tenancy (Workspaces)
# ═══════════════════════════════════════════════

async def test_create_workspace():
    """Create a workspace and get API key."""
    async with await client() as c:
        r = await c.post("/workspaces", json={
            "name": "Test Team",
            "description": "Team for testing"
        })
        assert r.status_code == 200
        assert r.json()["id"].startswith("ws-")
        assert r.json()["api_key"].startswith("ag-")
        assert r.json()["name"] == "Test Team"

async def test_workspace_default_exists():
    """Default workspace should exist from migration."""
    async with await client() as c:
        r = await c.get("/workspaces")
        assert r.status_code == 200
        ids = [ws["id"] for ws in r.json()["workspaces"]]
        assert "default" in ids

async def test_register_agent_in_workspace():
    """Agent registration should respect workspace_id."""
    async with await client() as c:
        # Create workspace
        ws = await c.post("/workspaces", json={"name": "Dev Team"})
        ws_id = ws.json()["id"]
        
        # Register agent in that workspace
        r = await c.post("/agents/register", json={
            "name": "WsBot",
            "daily_budget": 500,
            "workspace_id": ws_id
        })
        assert r.status_code == 200
        assert r.json()["workspace_id"] == ws_id

async def test_workspace_isolation_agents():
    """Agents from different workspaces should be isolated."""
    async with await client() as c:
        ws1 = (await c.post("/workspaces", json={"name": "Team A"})).json()["id"]
        ws2 = (await c.post("/workspaces", json={"name": "Team B"})).json()["id"]
        
        await c.post("/agents/register", json={"name": "BotA", "daily_budget": 100, "workspace_id": ws1})
        await c.post("/agents/register", json={"name": "BotB", "daily_budget": 200, "workspace_id": ws2})
        
        # Dashboard filtered to ws1 should only show BotA
        r = await c.get(f"/dashboard?workspace_id={ws1}")
        assert "BotA" in r.text
        assert "BotB" not in r.text

async def test_workspace_isolation_tools():
    """Tools from different workspaces should be isolated."""
    async with await client() as c:
        ws1 = (await c.post("/workspaces", json={"name": "Team X"})).json()["id"]
        
        r = await c.get(f"/tools?workspace_id=default")
        tools_before = r.json()["count"]
        
        await c.post("/tools/register", json={
            "name": "ws-only-tool",
            "cost_per_call": 5.0,
            "workspace_id": ws1
        })
        
        # Should NOT appear in default workspace
        r = await c.get(f"/tools?workspace_id=default")
        names = [t["name"] for t in r.json()["tools"]]
        assert "ws-only-tool" not in names
        
        # Should appear in ws1
        r = await c.get(f"/tools?workspace_id={ws1}")
        names = [t["name"] for t in r.json()["tools"]]
        assert "ws-only-tool" in names

async def test_default_workspace_backward_compat():
    """Old registrations without workspace_id should still work."""
    async with await client() as c:
        # Register without workspace_id
        r = await c.post("/agents/register", json={"name": "LegacyBot", "daily_budget": 100})
        assert r.status_code == 200
        assert r.json()["workspace_id"] == "default"
