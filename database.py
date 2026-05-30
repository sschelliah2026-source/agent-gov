"""
Database layer for agent-gov using SQLite + aiosqlite.

WHY SQLITE?
- Zero setup: no server process, no Docker, no config
- File-based: database is a single file (agent-gov.db)
- Perfect for MVP: handles thousands of agents easily
- Built into Python: no external dependencies
- Portable: copy the .db file to backup or migrate

WHY ASYNC (aiosqlite)?
- FastAPI is async by default
- aiosqlite wraps SQLite in async/await
- Prevents blocking the event loop during DB operations
- Pattern: async with db.execute("...") as cursor: await cursor.fetchall()

SCHEMA DESIGN:
  agents table:
    - key_hash (TEXT PRIMARY KEY): SHA-256 of API key (never store raw keys!)
    - name (TEXT): human-readable agent name
    - daily_budget (REAL): maximum spend per day in ₹
    - spent_today (REAL): running total for current day
    - calls_today (INTEGER): number of calls today
    - paused (INTEGER): 0=active, 1=paused (SQLite has no boolean)
    - created_at (TEXT): ISO 8601 timestamp
    - last_reset (TEXT): date of last daily budget reset
  
  cost_events table:
    - id (INTEGER PRIMARY KEY AUTOINCREMENT): unique event ID
    - timestamp (TEXT): ISO 8601 when call happened
    - agent_hash (TEXT FK): which agent made the call
    - tool_name (TEXT): which tool was called
    - cost (REAL): how much it cost in ₹
"""

import aiosqlite
import os
from datetime import datetime, date
import hashlib
import secrets
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "agent-gov.db")

# Test mode: use specified test database path
if os.environ.get("AGENT_GOV_TEST_DB"):
    DB_PATH = os.environ["AGENT_GOV_TEST_DB"]

# ──────────────────────────────────────────────
# LESSON 5: Database Connection Management
# 
# We use a single connection pool pattern.
# aiosqlite doesn't have connection pooling built in,
# so for MVP we use one connection with a mutex.
# For production, you'd use aiosqlite connection pool or switch to asyncpg.
# ──────────────────────────────────────────────

_db = None  # Singleton connection

async def get_db():
    """Get or create the database connection.
    
    Pattern: lazy initialization. First call creates the connection.
    All subsequent calls reuse it.
    """
    global _db
    if _db is None:
        _db = await aiosqlite.connect(DB_PATH)
        _db.row_factory = aiosqlite.Row  # Return rows as dict-like objects
        await _db.execute("PRAGMA journal_mode=WAL")  # Better concurrent reads
        await _db.execute("PRAGMA foreign_keys=ON")    # Enforce FK constraints
        await _init_schema(_db)
    return _db


async def _init_schema(db):
    """Create tables if they don't exist, run migrations.
    
    This is a MIGRATION. In production, you'd use Alembic or similar.
    For MVP, we use CREATE TABLE IF NOT EXISTS + ALTER TABLE ADD COLUMN.
    """
    # ── v0.5: Workspaces table ──
    await db.execute("""
        CREATE TABLE IF NOT EXISTS workspaces (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            api_key TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    
    await db.execute("""
        CREATE TABLE IF NOT EXISTS tools (
            name TEXT PRIMARY KEY,
            cost_per_call REAL NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            registered_at TEXT NOT NULL
        )
    """)
    
    await db.execute("""
        CREATE TABLE IF NOT EXISTS agents (
            key_hash TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            daily_budget REAL NOT NULL,
            spent_today REAL NOT NULL DEFAULT 0.0,
            calls_today INTEGER NOT NULL DEFAULT 0,
            paused INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            last_reset TEXT NOT NULL
        )
    """)
    
    await db.execute("""
        CREATE TABLE IF NOT EXISTS cost_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_hash TEXT NOT NULL,
            agent_name TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            tool_name TEXT NOT NULL,
            cost REAL NOT NULL,
            FOREIGN KEY (agent_hash) REFERENCES agents(key_hash)
        )
    """)
    
    # Index for fast queries: find all events for an agent
    await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_cost_events_agent 
        ON cost_events(agent_hash, timestamp)
    """)
    
    # ── Migrations: add workspace_id columns to existing tables ──
    # SQLite doesn't have IF NOT EXISTS for ALTER TABLE, so we check via PRAGMA
    async def _add_col_if_missing(table, col_name, col_def):
        cursor = await db.execute(f"PRAGMA table_info({table})")
        existing = {row[1] for row in await cursor.fetchall()}
        if col_name not in existing:
            await db.execute(f"ALTER TABLE {table} ADD COLUMN {col_def}")
    
    await _add_col_if_missing("tools", "workspace_id", "workspace_id TEXT REFERENCES workspaces(id)")
    await _add_col_if_missing("agents", "workspace_id", "workspace_id TEXT REFERENCES workspaces(id)")
    await _add_col_if_missing("cost_events", "workspace_id", "workspace_id TEXT REFERENCES workspaces(id)")
    
    # ── Ensure default workspace exists for existing data ──
    cursor = await db.execute("SELECT id FROM workspaces WHERE id = 'default'")
    if not await cursor.fetchone():
        default_key = generate_api_key()
        default_hash = hash_key(default_key)
        now = datetime.now().isoformat()
        await db.execute("""
            INSERT INTO workspaces (id, name, description, api_key, created_at)
            VALUES ('default', 'Default Workspace', 'Auto-created for backward compatibility', ?, ?)
        """, (default_hash, now))
    
    # Migrate NULL workspace_id to default
    for table in ("agents", "tools", "cost_events"):
        await db.execute(f"UPDATE {table} SET workspace_id = 'default' WHERE workspace_id IS NULL")
    
    await db.commit()


# ──────────────────────────────────────────────
# LESSON 6: CRUD Operations
# 
# CRUD = Create, Read, Update, Delete
# Every database table needs these four operations.
# We wrap them in async functions with clear names.
# ──────────────────────────────────────────────

def hash_key(api_key: str) -> str:
    """SHA-256 hash of API key. One-way — can't reverse."""
    return hashlib.sha256(api_key.encode()).hexdigest()

def generate_api_key() -> str:
    """Generate a new API key. 32 random hex chars + 'ag-' prefix."""
    return "ag-" + secrets.token_hex(16)

async def get_agent(key_hash: str) -> Optional[dict]:
    """SELECT agent by key hash. Returns None if not found."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM agents WHERE key_hash = ?", (key_hash,)
    )
    row = await cursor.fetchone()
    if row is None:
        return None
    
    # Convert SQLite Row to dict
    return {
        "key_hash": row["key_hash"],
        "name": row["name"],
        "daily_budget": row["daily_budget"],
        "spent_today": row["spent_today"],
        "calls_today": row["calls_today"],
        "paused": bool(row["paused"]),
        "created_at": row["created_at"],
        "last_reset": row["last_reset"]
    }

async def update_agent_spend(key_hash: str, cost: float) -> dict:
    """UPDATE agent's spent_today and calls_today after a successful call.
    
    Uses a TRANSACTION to ensure atomicity:
    If the UPDATE fails, the SELECT still happened — inconsistent.
    With BEGIN/COMMIT, both or neither happen.
    """
    db = await get_db()
    
    await db.execute("""
        UPDATE agents 
        SET spent_today = spent_today + ?, calls_today = calls_today + 1
        WHERE key_hash = ?
    """, (cost, key_hash))
    await db.commit()
    
    # Fetch updated state
    return await get_agent(key_hash)

async def pause_agent(key_hash: str) -> None:
    """Set agent paused = 1."""
    db = await get_db()
    await db.execute("UPDATE agents SET paused = 1 WHERE key_hash = ?", (key_hash,))
    await db.commit()

async def resume_agent(key_hash: str) -> dict:
    """Resume agent: set paused = 0, reset spent_today, update last_reset."""
    db = await get_db()
    today = date.today().isoformat()
    
    await db.execute("""
        UPDATE agents 
        SET paused = 0, spent_today = 0.0, calls_today = 0, last_reset = ?
        WHERE key_hash = ?
    """, (today, key_hash))
    await db.commit()
    
    return await get_agent(key_hash)

async def log_cost_event(key_hash: str, agent_name: str, tool_name: str, cost: float) -> None:
    """INSERT a cost event for analytics."""
    db = await get_db()
    await db.execute("""
        INSERT INTO cost_events (agent_hash, agent_name, timestamp, tool_name, cost)
        VALUES (?, ?, ?, ?, ?)
    """, (key_hash, agent_name, datetime.now().isoformat(), tool_name, cost))
    await db.commit()

async def get_recent_events(limit: int = 50) -> list[dict]:
    """Get recent cost events for analytics."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM cost_events ORDER BY id DESC LIMIT ?", (limit,)
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


# ── Tool lookup (used by proxy/call) ──

async def get_tool(name: str) -> Optional[dict]:
    """SELECT a tool by name. Returns None if not found."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM tools WHERE name = ?", (name,)
    )
    row = await cursor.fetchone()
    if row is None:
        return None
    return {
        "name": row["name"],
        "cost_per_call": row["cost_per_call"],
        "description": row["description"],
        "registered_at": row["registered_at"]
    }


# ──────────────────────────────────────────────
# LESSON 10: Daily Budget Auto-Reset
# 
# Agents have a "daily" budget that resets at midnight.
# Instead of a cron job, we check on every proxy call:
# "Is today different from last_reset?"
# If yes → reset spent_today and calls_today to 0.
# 
# This is called LAZY EVALUATION — do work only when needed.
# ──────────────────────────────────────────────

async def check_and_reset_budget(agent: dict) -> dict:
    """Auto-reset agent budget if today != last_reset.
    
    This runs BEFORE every proxy call. If the agent's
    last_reset date is NOT today, their counters reset to 0.
    Only affects ACTIVE agents (paused agents keep their state).
    
    Returns the updated agent dict (fresh from DB).
    """
    today = date.today().isoformat()
    
    # No reset needed if already on today's date
    if agent["last_reset"] == today:
        return agent
    
    # Don't auto-reset paused agents — they need manual resume
    if agent["paused"]:
        return agent
    
    # Auto-reset: zero out counters, update date
    return await reset_daily_budget(agent["key_hash"])

async def reset_daily_budget(key_hash: str) -> dict:
    """Reset an agent's daily spend counters to 0.
    
    Can be called:
    - Automatically (via check_and_reset_budget at day boundary)
    - Manually (via POST /agents/{key}/reset endpoint)
    - By resume (resume already resets via resume_agent)
    """
    db = await get_db()
    today = date.today().isoformat()
    
    await db.execute("""
        UPDATE agents 
        SET spent_today = 0.0, calls_today = 0, last_reset = ?
        WHERE key_hash = ?
    """, (today, key_hash))
    await db.commit()
    
    return await get_agent(key_hash)


# ──────────────────────────────────────────────
# LESSON 11: Workspace CRUD (Multi-Tenancy)
# 
# Workspaces isolate agents, tools, and costs by team/project.
# Each workspace has its own agents, tools, and event history.
# The "default" workspace provides backward compatibility.
# ──────────────────────────────────────────────

async def create_workspace(name: str, description: str = "") -> dict:
    """CREATE a new workspace with its own API key."""
    db = await get_db()
    workspace_id = "ws-" + secrets.token_hex(8)
    api_key = generate_api_key()
    key_hash = hash_key(api_key)
    now = datetime.now().isoformat()
    
    await db.execute("""
        INSERT INTO workspaces (id, name, description, api_key, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (workspace_id, name, description, key_hash, now))
    await db.commit()
    
    return {
        "id": workspace_id,
        "name": name,
        "description": description,
        "api_key": api_key,  # Raw key, one-time only!
        "created_at": now
    }

async def get_all_workspaces() -> list[dict]:
    """SELECT all workspaces."""
    db = await get_db()
    cursor = await db.execute("SELECT * FROM workspaces ORDER BY created_at ASC")
    rows = await cursor.fetchall()
    return [{
        "id": row["id"],
        "name": row["name"],
        "description": row["description"],
        "api_key": "***hashed***",  # Never expose raw hashed keys
        "created_at": row["created_at"]
    } for row in rows]

async def workspace_exists(workspace_id: str) -> bool:
    """Check if a workspace exists."""
    db = await get_db()
    cursor = await db.execute("SELECT 1 FROM workspaces WHERE id = ?", (workspace_id,))
    return await cursor.fetchone() is not None


# ── Updated CRUD with workspace_id support (backward compatible) ──

async def create_agent(name: str, daily_budget: float, workspace_id: str = "default") -> dict:
    """INSERT a new agent in a workspace."""
    db = await get_db()
    api_key = generate_api_key()
    key_hash = hash_key(api_key)
    now = datetime.now().isoformat()
    today = date.today().isoformat()
    
    await db.execute("""
        INSERT INTO agents (key_hash, name, daily_budget, spent_today, calls_today, paused, created_at, last_reset, workspace_id)
        VALUES (?, ?, ?, 0.0, 0, 0, ?, ?, ?)
    """, (key_hash, name, daily_budget, now, today, workspace_id))
    await db.commit()
    
    return {
        "api_key": api_key,
        "name": name,
        "daily_budget": daily_budget,
        "workspace_id": workspace_id
    }

async def get_all_agents(workspace_id: str = None) -> list[dict]:
    """SELECT all agents, optionally filtered by workspace."""
    db = await get_db()
    if workspace_id:
        cursor = await db.execute(
            "SELECT * FROM agents WHERE workspace_id = ? ORDER BY paused DESC, spent_today DESC",
            (workspace_id,)
        )
    else:
        cursor = await db.execute("SELECT * FROM agents ORDER BY paused DESC, spent_today DESC")
    rows = await cursor.fetchall()
    return [
        {
            "key_hash": row["key_hash"],
            "name": row["name"],
            "daily_budget": row["daily_budget"],
            "spent_today": row["spent_today"],
            "calls_today": row["calls_today"],
            "paused": bool(row["paused"]),
            "created_at": row["created_at"],
            "last_reset": row["last_reset"],
            "workspace_id": row["workspace_id"]
        }
        for row in rows
    ]

async def get_stats(workspace_id: str = None) -> dict:
    """Get aggregate statistics, optionally filtered by workspace."""
    db = await get_db()
    
    if workspace_id:
        cursor = await db.execute("SELECT COUNT(*) as count FROM agents WHERE workspace_id = ?", (workspace_id,))
        agent_count = (await cursor.fetchone())["count"]
        cursor = await db.execute("SELECT COUNT(*) as count FROM cost_events WHERE workspace_id = ?", (workspace_id,))
        event_count = (await cursor.fetchone())["count"]
    else:
        cursor = await db.execute("SELECT COUNT(*) as count FROM agents")
        agent_count = (await cursor.fetchone())["count"]
        cursor = await db.execute("SELECT COUNT(*) as count FROM cost_events")
        event_count = (await cursor.fetchone())["count"]
    
    cursor = await db.execute("SELECT COUNT(*) as count FROM tools")
    tools_count = (await cursor.fetchone())["count"]
    
    return {
        "agents_registered": agent_count,
        "total_calls_tracked": event_count,
        "tools_registered": tools_count
    }

async def register_tool(name: str, cost_per_call: float, description: str = "", workspace_id: str = "default") -> dict:
    """INSERT or UPDATE a tool, scoped to a workspace."""
    db = await get_db()
    now = datetime.now().isoformat()
    
    await db.execute("""
        INSERT INTO tools (name, cost_per_call, description, registered_at, workspace_id)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(name) DO UPDATE SET
            cost_per_call = excluded.cost_per_call,
            description = excluded.description,
            registered_at = excluded.registered_at,
            workspace_id = excluded.workspace_id
    """, (name, cost_per_call, description, now, workspace_id))
    await db.commit()
    
    return {
        "name": name,
        "cost_per_call": cost_per_call,
        "description": description,
        "workspace_id": workspace_id
    }

async def get_all_tools(workspace_id: str = None) -> list[dict]:
    """SELECT all tools, optionally filtered by workspace."""
    db = await get_db()
    if workspace_id:
        cursor = await db.execute("SELECT * FROM tools WHERE workspace_id = ? ORDER BY name ASC", (workspace_id,))
    else:
        cursor = await db.execute("SELECT * FROM tools ORDER BY name ASC")
    rows = await cursor.fetchall()
    return [{
        "name": row["name"],
        "cost_per_call": row["cost_per_call"],
        "description": row["description"],
        "registered_at": row["registered_at"],
        "workspace_id": row["workspace_id"]
    } for row in rows]

async def get_tool_spend_stats(workspace_id: str = None) -> list[dict]:
    """Get per-tool spend stats, optionally filtered by workspace."""
    db = await get_db()
    if workspace_id:
        cursor = await db.execute("""
            SELECT 
                tool_name,
                COUNT(*) as total_calls,
                SUM(cost) as total_spent,
                AVG(cost) as avg_cost,
                COUNT(DISTINCT agent_hash) as agent_count
            FROM cost_events
            WHERE workspace_id = ?
            GROUP BY tool_name
            ORDER BY total_spent DESC
        """, (workspace_id,))
    else:
        cursor = await db.execute("""
            SELECT 
                tool_name,
                COUNT(*) as total_calls,
                SUM(cost) as total_spent,
                AVG(cost) as avg_cost,
                COUNT(DISTINCT agent_hash) as agent_count
            FROM cost_events
            GROUP BY tool_name
            ORDER BY total_spent DESC
        """)
    rows = await cursor.fetchall()
    return [{
        "tool_name": row["tool_name"],
        "total_calls": row["total_calls"],
        "total_spent": round(row["total_spent"], 2) if row["total_spent"] else 0,
        "avg_cost": round(row["avg_cost"], 2) if row["avg_cost"] else 0,
        "agent_count": row["agent_count"]
    } for row in rows]


async def close_db():
    """Close the database connection on shutdown."""
    global _db
    if _db:
        await _db.close()
        _db = None
