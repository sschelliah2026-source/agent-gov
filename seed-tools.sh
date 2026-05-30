#!/bin/bash
# seed-tools.sh — Register common tools with agent-gov
# Usage: bash seed-tools.sh [host:port] [workspace_id]
#   Default host: localhost:8000
#   Default workspace: default

HOST="${1:-localhost:8000}"
WORKSPACE="${2:-default}"
BASE="http://$HOST"

echo "╔══════════════════════════════════════════════╗"
echo "║        🛡  agent-gov  Tool Seed (Bash)       ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
echo "Server: $BASE"
echo "Workspace: $WORKSPACE"
echo ""

# Check server
if ! curl -sf "$BASE/" > /dev/null 2>&1; then
    echo "❌ Cannot connect to agent-gov at $BASE"
    echo "   Start: agent-gov start  (or: python app.py)"
    exit 1
fi

echo "✅ Connected!"
echo ""

# Register tools
register() {
    local name="$1"
    local cost="$2"
    local desc="$3"
    local resp
    resp=$(curl -sf -X POST "$BASE/tools/register" \
        -H "Content-Type: application/json" \
        -d "{\"name\": \"$name\", \"cost_per_call\": $cost, \"description\": \"$desc\", \"workspace_id\": \"$WORKSPACE\"}" 2>&1)
    if [ $? -eq 0 ]; then
        echo "  ✅ $name"
    else
        echo "  ❌ $name — $resp"
    fi
}

echo "Registering tools..."

# LLM APIs
register "openai-gpt4o"         0.15  "GPT-4o (~1K tokens output)"
register "openai-gpt4o-mini"    0.02  "GPT-4o-mini (~1K tokens output)"
register "anthropic-sonnet"     0.12  "Claude 3.5 Sonnet (~1K tokens output)"
register "deepseek-v3"          0.02  "DeepSeek V3 (~1K tokens)"
register "gemini-flash"         0.01  "Gemini 2.5 Flash (~1K tokens)"

# Web & Browser
register "firecrawl-scrape"     0.10  "Firecrawl page scrape"
register "tavily-search"        0.03  "Tavily AI search"
register "browser-use"          0.50  "Browser Use automation session"

# Communication
register "twilio-sms"           1.50  "Twilio SMS (India)"
register "sendgrid-email"       0.03  "SendGrid email"

# Media
register "dalle3"               0.60  "DALL-E 3 image"
register "elevenlabs-tts"       0.05  "ElevenLabs TTS"

# Code
register "e2b-sandbox"          0.05  "E2B cloud sandbox"

echo ""
echo "────────────────────────────────────────"
echo "✅ Done!"
echo ""
echo "  List tools:  $BASE/tools?workspace_id=$WORKSPACE"
echo "  Dashboard:   $BASE/dashboard?workspace_id=$WORKSPACE"
