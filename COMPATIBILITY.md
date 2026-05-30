# 🛡 agent-gov Tool Compatibility Guide

> **How agent-gov works with any tool your AI agent might call.**

---

## How agent-gov Integrates With Tools

agent-gov is **not a transparent proxy** (it doesn't intercept API calls). Instead, it's a **budget-checking sidecar**:

```
┌────────────────────────────────────────────┐
│           Your AI Agent Code               │
│                                            │
│  1. POST /proxy/call (agent_key, tool,     │
│     estimated_cost)                        │
│                                            │
│  2. agent-gov checks:                      │
│     ✓ Is the API key valid?                │
│     ✓ Is the agent paused?                 │
│     ✓ Does the budget allow this call?     │
│     ✓ What's the real tool cost?           │
│     ✓ Auto-reset if new day?               │
│                                            │
│  3. If approved → call the real tool       │
│     If denied  → handle the 429            │
└────────────────────────────────────────────┘
```

**This means agent-gov works with ANY tool** — it doesn't need to modify the tool itself. You just add one HTTP call before the real tool call.

---

## 🟢 Fully Compatible Tools

### 1. LLM APIs

These are the most common use case. Register each model as a tool with its per-call cost.

| Provider | Models | Registration Example |
|----------|--------|---------------------|
| **OpenAI** | GPT-4o, GPT-4o-mini, o1, o3-mini | `{"name": "openai-gpt4o", "cost_per_call": 0.15}` |
| **Anthropic** | Claude 3.5 Sonnet, Haiku, Opus | `{"name": "anthropic-sonnet", "cost_per_call": 0.12}` |
| **DeepSeek** | V3, R1 | `{"name": "deepseek-v3", "cost_per_call": 0.02}` |
| **Google** | Gemini 2.5 Pro, Flash | `{"name": "gemini-flash", "cost_per_call": 0.01}` |
| **Together AI** | Mixtral, Llama, Qwen | `{"name": "together-mixtral", "cost_per_call": 0.03}` |
| **Fireworks** | Llama 3, Qwen 2.5 | `{"name": "fireworks-llama", "cost_per_call": 0.02}` |
| **Groq** | Llama 3, Mixtral (fast inference) | `{"name": "groq-llama", "cost_per_call": 0.01}` |
| **Any OpenAI-compatible** | vLLM, TGI, Ollama, LocalAI | `{"name": "ollama-qwen3", "cost_per_call": 0.001}` |

**Registering costs (₹):**
```bash
curl -X POST http://localhost:8000/tools/register \
  -H "Content-Type: application/json" \
  -d '{"name": "openai-gpt4o", "cost_per_call": 0.15, "description": "GPT-4o API call per 1K tokens"}'
```

**Integration pattern (Python):**
```python
import requests

GOV_URL = "http://localhost:8000"
AGENT_KEY = "ag-abc123..."  # From POST /agents/register

def call_openai(prompt):
    # Step 1: Check with agent-gov first
    gov_resp = requests.post(f"{GOV_URL}/proxy/call", json={
        "agent_key": AGENT_KEY,
        "tool_name": "openai-gpt4o",
        "estimated_cost": 0.15
    })
    
    if gov_resp.status_code == 429:
        raise Exception(f"Budget exceeded! Agent paused. {gov_resp.json()['detail']}")
    
    # Step 2: Make the actual call
    from openai import OpenAI
    client = OpenAI()
    return client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}]
    )
```

---

### 2. Web & Browser Tools

| Tool | Cost Model | Register As |
|------|-----------|-------------|
| **Firecrawl** | Per-page scrape (₹0.10–₹0.50/page) | `{"name": "firecrawl-scrape", "cost_per_call": 0.10}` |
| **SerpAPI** | Per search (₹0.05/search) | `{"name": "serpapi-search", "cost_per_call": 0.05}` |
| **Tavily** | Per AI search (₹0.03/search) | `{"name": "tavily-search", "cost_per_call": 0.03}` |
| **Brave Search** | Per query (₹0.01/query) | `{"name": "brave-search", "cost_per_call": 0.01}` |
| **Browser Use** | Per session (₹0.50/session) | `{"name": "browser-use", "cost_per_call": 0.50}` |
| **Playwright Cloud** | Per test run | `{"name": "playwright-cloud", "cost_per_call": 0.08}` |

---

### 3. Communication APIs

| Tool | Cost Model | Register As |
|------|-----------|-------------|
| **Twilio SMS** | ₹0.75–₹3.00/SMS | `{"name": "twilio-sms", "cost_per_call": 1.50}` |
| **SendGrid** | ₹0.03/email (after free tier) | `{"name": "sendgrid-email", "cost_per_call": 0.03}` |
| **WhatsApp Business** | ₹0.50/conversation | `{"name": "whatsapp-msg", "cost_per_call": 0.50}` |
| **Slack API** | Free (but track rate limits) | `{"name": "slack-api", "cost_per_call": 0.0}` |

---

### 4. Media Generation

| Tool | Cost Model | Register As |
|------|-----------|-------------|
| **DALL-E 3** | ₹0.40–₹0.80/image | `{"name": "dalle3", "cost_per_call": 0.60}` |
| **Stable Diffusion** | ₹0.02/image (self-hosted) or ₹0.10 (API) | `{"name": "sdxl-api", "cost_per_call": 0.10}` |
| **ElevenLabs TTS** | ₹0.01/char | `{"name": "elevenlabs-tts", "cost_per_call": 0.05}` |
| **Runway Gen-3** | ₹0.50–₹2.00/video | `{"name": "runway-gen3", "cost_per_call": 1.00}` |
| **Suno AI** | ₹0.10/song | `{"name": "suno-music", "cost_per_call": 0.10}` |

---

### 5. Code Execution

| Tool | Cost Model | Register As |
|------|-----------|-------------|
| **E2B Sandbox** | ₹0.03–₹0.10/session | `{"name": "e2b-sandbox", "cost_per_call": 0.05}` |
| **Modal** | ₹0.01/invocation | `{"name": "modal-func", "cost_per_call": 0.01}` |
| **GitHub Codespaces** | ₹0.56/hour | `{"name": "codespace", "cost_per_call": 0.56}` |

---

### 6. Data & Knowledge APIs

| Tool | Cost Model | Register As |
|------|-----------|-------------|
| **Exa** | Per search + content (₹0.02–0.10) | `{"name": "exa-search", "cost_per_call": 0.05}` |
| **Wolfram Alpha** | Per query (₹0.07/query) | `{"name": "wolfram-alpha", "cost_per_call": 0.07}` |
| **SEC EDGAR** | Free (track for analytics) | `{"name": "sec-edgar", "cost_per_call": 0.0}` |
| **NewsAPI** | ₹0.03/news article | `{"name": "news-api", "cost_per_call": 0.03}` |

---

## 🔧 Integration Patterns

### Pattern A: LangChain (Callback Handler)

```python
from langchain.callbacks.base import BaseCallbackHandler
import requests

class AgentGovCallback(BaseCallbackHandler):
    def __init__(self, gov_url: str, agent_key: str):
        self.gov_url = gov_url
        self.agent_key = agent_key
    
    def on_llm_start(self, serialized, prompts, **kwargs):
        model = serialized.get("kwargs", {}).get("model_name", "unknown")
        resp = requests.post(f"{self.gov_url}/proxy/call", json={
            "agent_key": self.agent_key,
            "tool_name": f"langchain-{model}",
            "estimated_cost": 0.05
        })
        if resp.status_code == 429:
            raise Exception("Agent paused — budget exceeded")

# Usage
llm = ChatOpenAI(model="gpt-4o", callbacks=[AgentGovCallback(...)])
```

### Pattern B: Decorator (Any Python Function)

```python
import requests
from functools import wraps

GOV_URL = "http://localhost:8000"
AGENT_KEY = "ag-abc123..."

def gov_gate(tool_name: str, cost: float = 0.05):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            resp = requests.post(f"{GOV_URL}/proxy/call", json={
                "agent_key": AGENT_KEY,
                "tool_name": tool_name,
                "estimated_cost": cost
            })
            if resp.status_code == 429:
                raise Exception(f"Agent paused: {resp.json()['detail']}")
            return func(*args, **kwargs)
        return wrapper
    return decorator

@gov_gate("openai-gpt4", 0.15)
def get_weather(city: str):
    return f"The weather in {city} is sunny"
```

### Pattern C: OpenAI Tool/Function Call Wrapper

```python
import json
import requests

GOV_URL = "http://localhost:8000"

class GovernedTool:
    """Wrap any OpenAI function tool with agent-gov budget checking."""
    
    def __init__(self, name: str, func, cost: float, description: str):
        self.name = name
        self.func = func
        self.cost = cost
        self.openai_spec = {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": {"type": "object", "properties": {}}
            }
        }
    
    def check_budget(self, agent_key: str):
        resp = requests.post(f"{GOV_URL}/proxy/call", json={
            "agent_key": agent_key,
            "tool_name": self.name,
            "estimated_cost": self.cost
        })
        return resp.status_code == 200
    
    def execute(self, agent_key: str, **kwargs):
        if not self.check_budget(agent_key):
            return {"error": "Budget exceeded — agent paused"}
        return self.func(**kwargs)
```

### Pattern D: MCP Server Wrapper

If you run MCP servers, wrap them with agent-gov:

```python
# MCP server with agent-gov cost tracking
from mcp.server import Server
import requests

GOV_URL = "http://localhost:8000"
server = Server("my-mcp-server")

@server.tool()
async def search_web(query: str, agent_key: str) -> str:
    # Check budget first
    resp = requests.post(f"{GOV_URL}/proxy/call", json={
        "agent_key": agent_key,
        "tool_name": "web-search",
        "estimated_cost": 0.05
    })
    if resp.status_code == 429:
        return f"❌ Budget exceeded: {resp.json()['detail']}"
    
    # Proceed with actual search
    return perform_search(query)
```

---

## 📋 One-Click Tool Presets

For convenience, here's a bulk registration script you can run after starting agent-gov:

```bash
# Register common tools with realistic costs (₹)
curl -X POST http://localhost:8000/tools/register \
  -H 'Content-Type: application/json' \
  -d '[
    {"name": "openai-gpt4o", "cost_per_call": 0.15},
    {"name": "openai-gpt4o-mini", "cost_per_call": 0.02},
    {"name": "anthropic-sonnet", "cost_per_call": 0.12},
    {"name": "deepseek-v3", "cost_per_call": 0.02},
    {"name": "gemini-flash", "cost_per_call": 0.01},
    {"name": "firecrawl-scrape", "cost_per_call": 0.10},
    {"name": "tavily-search", "cost_per_call": 0.03},
    {"name": "twilio-sms", "cost_per_call": 1.50},
    {"name": "sendgrid-email", "cost_per_call": 0.03},
    {"name": "dalle3", "cost_per_call": 0.60},
    {"name": "elevenlabs-tts", "cost_per_call": 0.05},
    {"name": "e2b-sandbox", "cost_per_call": 0.05},
    {"name": "browser-use", "cost_per_call": 0.50}
  ]'
```

---

## 🎯 Summary

| Category | Compatible? | Pattern |
|----------|------------|---------|
| Any HTTP API | ✅ Yes | Call agent-gov before the real API |
| Any LLM Provider | ✅ Yes | Register as tool, call before inference |
| Any Web Tool | ✅ Yes | Wrap the web call with a budget check |
| Any Communication API | ✅ Yes | Check budget before sending messages |
| Any Media Gen API | ✅ Yes | Register per-call cost |
| MCP Servers | ✅ Yes | Wrap tool handler with cost check |
| LangChain Agents | ✅ Yes | Use callback handler |
| Custom Agents | ✅ Yes | Use decorator pattern |

**Bottom line:** If your agent can call it, agent-gov can govern it. The only requirement is one HTTP call before the real tool call.
