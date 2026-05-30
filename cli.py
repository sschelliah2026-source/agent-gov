#!/usr/bin/env python3
"""
agent-gov CLI — Start, manage, and monitor your agent cost governance server.

Usage:
    agent-gov start          Start the governance server (default: port 8000)
    agent-gov start --port 9000
    agent-gov --help
"""

import argparse
import sys
import os

DESCRIPTION = """
🛡 agent-gov — AI Agent Cost Governance Platform

A reverse proxy that sits between your AI agents and their tools.
Tracks costs, enforces budgets, auto-pauses overspending agents.

Quick start:
  agent-gov start          # Start server on port 8000
  curl localhost:8000       # Health check
"""


def main():
    parser = argparse.ArgumentParser(
        prog="agent-gov",
        description=DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Start command
    start_parser = subparsers.add_parser("start", help="Start the governance server")
    start_parser.add_argument(
        "--port", "-p",
        type=int,
        default=8000,
        help="Port to listen on (default: 8000)"
    )
    start_parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)"
    )
    start_parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development"
    )
    
    # Version command
    subparsers.add_parser("version", help="Show version")
    
    # Status command
    status_parser = subparsers.add_parser("status", help="Check if the server is running")
    status_parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to check (default: 8000)"
    )
    
    args = parser.parse_args()
    
    if args.command == "start":
        _start_server(args.host, args.port, args.reload)
    elif args.command == "version":
        print("agent-gov v0.5.0")
    elif args.command == "status":
        _check_status(args.port)
    else:
        parser.print_help()


def _start_server(host: str, port: int, reload: bool):
    """Start the FastAPI server."""
    try:
        import uvicorn
    except ImportError:
        print("❌ Missing dependencies. Run: pip install agent-gov")
        sys.exit(1)
    
    # Ensure we can import the app
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    
    print(f"""
╔═══════════════════════════════════════════════╗
║           🛡  agent-gov  v0.5                 ║
║   AI Agent Cost Governance Platform           ║
╚═══════════════════════════════════════════════╝

  Dashboard : http://{host if host != '0.0.0.0' else 'localhost'}:{port}/dashboard
  API Docs  : http://{host if host != '0.0.0.0' else 'localhost'}:{port}/docs
  Health    : http://{host if host != '0.0.0.0' else 'localhost'}:{port}/

  Register an agent:
    curl -X POST http://{host if host != '0.0.0.0' else 'localhost'}:{port}/agents/register \\
      -H 'Content-Type: application/json' \\
      -d '{{"name": "My Agent", "daily_budget": 500}}'

  Press Ctrl+C to stop.
""")
    
    uvicorn.run(
        "app:app",
        host=host,
        port=port,
        reload=reload
    )


def _check_status(port: int):
    """Check if the server is running."""
    try:
        import httpx
        r = httpx.get(f"http://localhost:{port}/", timeout=3)
        if r.status_code == 200:
            data = r.json()
            print(f"✅ agent-gov is running (v{data.get('version', '?')})")
            print(f"   Agents registered: {data.get('agents_registered', '?')}")
            print(f"   Calls tracked: {data.get('total_calls_tracked', '?')}")
            print(f"   Dashboard: http://localhost:{port}/dashboard")
        else:
            print(f"⚠️  Server responded with status {r.status_code}")
    except Exception as e:
        print(f"❌ agent-gov is not running on port {port}")
        print(f"   Start it with: agent-gov start --port {port}")
        print(f"   Error: {e}")


if __name__ == "__main__":
    main()
