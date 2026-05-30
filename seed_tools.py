#!/usr/bin/env python3
"""
Seed script for agent-gov — registers common tools with realistic costs.

Usage:
    # Default: registers on localhost:8000
    python seed_tools.py

    # Custom host/port
    python seed_tools.py --host http://localhost:7999

    # Custom workspace
    python seed_tools.py --workspace ws-abc123

This registers 15+ common AI tools with their per-call costs in ₹ (Indian Rupees).
Costs are approximate — adjust them based on your actual API pricing.
"""

import argparse
import json
import sys
import urllib.request
import urllib.error

# ── Tool Presets ──────────────────────────────────────
# Costs are per-call in ₹. Based on typical API pricing.
# Adjust these to match your actual API usage patterns.

TOOLS = [
    # ── LLM APIs ──
    {"name": "openai-gpt4o", "cost_per_call": 0.15, "description": "GPT-4o (~1K tokens output)"},
    {"name": "openai-gpt4o-mini", "cost_per_call": 0.02, "description": "GPT-4o-mini (~1K tokens output)"},
    {"name": "openai-o1", "cost_per_call": 0.60, "description": "OpenAI o1 (reasoning, ~1K tokens)"},
    {"name": "openai-o3-mini", "cost_per_call": 0.04, "description": "OpenAI o3-mini (~1K tokens)"},
    {"name": "anthropic-sonnet", "cost_per_call": 0.12, "description": "Claude 3.5 Sonnet (~1K tokens output)"},
    {"name": "anthropic-haiku", "cost_per_call": 0.02, "description": "Claude 3.5 Haiku (~1K tokens output)"},
    {"name": "deepseek-v3", "cost_per_call": 0.02, "description": "DeepSeek V3 (~1K tokens)"},
    {"name": "deepseek-r1", "cost_per_call": 0.05, "description": "DeepSeek R1 (reasoning, ~1K tokens)"},
    {"name": "gemini-flash", "cost_per_call": 0.01, "description": "Gemini 2.5 Flash (~1K tokens)"},
    {"name": "gemini-pro", "cost_per_call": 0.05, "description": "Gemini 2.5 Pro (~1K tokens)"},
    {"name": "groq-llama", "cost_per_call": 0.005, "description": "Groq Llama 3 (fast inference)"},
    
    # ── Web & Browser ──
    {"name": "firecrawl-scrape", "cost_per_call": 0.10, "description": "Firecrawl page scrape"},
    {"name": "tavily-search", "cost_per_call": 0.03, "description": "Tavily AI search query"},
    {"name": "serpapi-search", "cost_per_call": 0.05, "description": "SerpAPI search query"},
    {"name": "brave-search", "cost_per_call": 0.01, "description": "Brave Search API query"},
    {"name": "browser-use", "cost_per_call": 0.50, "description": "Browser Use automation session"},
    
    # ── Communication ──
    {"name": "twilio-sms", "cost_per_call": 1.50, "description": "Twilio SMS (India)"},
    {"name": "sendgrid-email", "cost_per_call": 0.03, "description": "SendGrid transactional email"},
    
    # ── Media Generation ──
    {"name": "dalle3", "cost_per_call": 0.60, "description": "DALL-E 3 image generation"},
    {"name": "elevenlabs-tts", "cost_per_call": 0.05, "description": "ElevenLabs TTS (~500 chars)"},
    
    # ── Code Execution ──
    {"name": "e2b-sandbox", "cost_per_call": 0.05, "description": "E2B cloud code sandbox"},
    {"name": "modal-func", "cost_per_call": 0.01, "description": "Modal serverless function call"},
    
    # ── Data APIs ──
    {"name": "exa-search", "cost_per_call": 0.05, "description": "Exa search + content retrieval"},
    {"name": "wolfram-alpha", "cost_per_call": 0.07, "description": "Wolfram Alpha computation query"},
]

WORKSPACE_ID = "default"


def register_tool(url: str, tool: dict, workspace: str) -> bool:
    """Register a single tool. Returns True on success."""
    payload = {**tool, "workspace_id": workspace}
    data = json.dumps(payload).encode("utf-8")
    
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = json.loads(resp.read().decode())
            status = body.get("status", "?")
            print(f"  ✅ {tool['name']:25s}  ₹{tool['cost_per_call']:<8.3f}  ({status})")
            return True
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"  ❌ {tool['name']:25s}  HTTP {e.code}: {body[:80]}")
        return False
    except Exception as e:
        print(f"  ⚠️  {tool['name']:25s}  {e}")
        return False


def check_server(base_url: str) -> bool:
    """Verify the agent-gov server is running."""
    try:
        req = urllib.request.Request(f"{base_url}/", method="GET")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            print(f"✅ Connected to agent-gov v{data.get('version', '?')}")
            print(f"   Agents: {data.get('agents_registered', '?')}  Calls: {data.get('total_calls_tracked', '?')}")
            return True
    except Exception as e:
        print(f"❌ Cannot connect to agent-gov at {base_url}")
        print(f"   Error: {e}")
        print(f"   Start the server with: agent-gov start  (or: python app.py)")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Seed agent-gov with common tool presets"
    )
    parser.add_argument(
        "--host",
        default="http://localhost:8000",
        help="agent-gov server URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--workspace",
        default="default",
        help="Workspace ID to register tools under (default: default)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Just list the tools and their costs, don't register",
    )
    parser.add_argument(
        "--filter",
        default=None,
        help="Only register tools matching this keyword (e.g., 'openai', 'deepseek')",
    )
    
    args = parser.parse_args()
    base_url = args.host.rstrip("/")
    register_url = f"{base_url}/tools/register"
    
    # Filter tools if --filter provided
    tools = TOOLS
    if args.filter:
        keyword = args.filter.lower()
        tools = [t for t in tools if keyword in t["name"].lower() or keyword in t["description"].lower()]
        if not tools:
            print(f"No tools match filter: '{args.filter}'")
            sys.exit(1)
    
    # ── Just list? ──
    if args.list:
        print(f"\n{'Tool Name':25s}  {'Cost/ Call (₹)':16s}  Description")
        print("-" * 75)
        for t in tools:
            print(f"{t['name']:25s}  ₹{t['cost_per_call']:<13.3f}  {t['description']}")
        print(f"\n{len(tools)} tools listed. Run without --list to register.")
        return
    
    # ── Register ──
    print(f"\n╔══════════════════════════════════════════════╗")
    print(f"║        🛡  agent-gov  Tool Seed              ║")
    print(f"╚══════════════════════════════════════════════╝")
    print(f"\nRegistering {len(tools)} tools in workspace '{args.workspace}'...\n")
    
    if not check_server(base_url):
        sys.exit(1)
    
    success = 0
    failed = 0
    for tool in tools:
        if register_tool(register_url, tool, args.workspace):
            success += 1
        else:
            failed += 1
    
    print(f"\n{'─' * 40}")
    print(f"✅ {success} tools registered")
    if failed:
        print(f"❌ {failed} tools failed")
    
    # ── Summary ──
    print(f"\n📊  Workspace: {args.workspace}")
    print(f"    Get dashboard: {base_url}/dashboard?workspace_id={args.workspace}")
    print(f"    List tools:    {base_url}/tools?workspace_id={args.workspace}")
    print(f"    View presets:  python seed_tools.py --list\n")


if __name__ == "__main__":
    main()
