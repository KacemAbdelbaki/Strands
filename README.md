# Strands Personal Assistant — MCP Server

A personal-assistant system built with [Strands Agents](https://strandsagents.com) (Python), wrapped in an MCP server via [FastMCP](https://github.com/modelcontextprotocol/python-sdk). Callable from Claude Desktop, Claude Code, MCP Inspector, or any MCP client.

**Free models only** — no paid API keys required for base operation.

---

## Features

| Phase | Capability | Status |
|-------|-----------|--------|
| 1 | Current time, persistent memory, web search | ✅ |
| 2 | Google Calendar (via MCP) | 🔲 |
| 3 | Gmail read-only (via MCP) | 🔲 |
| 4 | File-based notes | 🔲 |

---

## Prerequisites

- **Python 3.11+**
- **Node.js + npm** — needed for `npx` MCP servers (Phases 2-3) and MCP Inspector
- **Ollama** — **required** regardless of model provider (memory always runs locally)
  - Install: <https://ollama.com/download>
  - Ensure `ollama serve` is running
- **Docker** (optional, for containerized deployment)

### Pull Required Ollama Models

```bash
# Required — memory (fact extraction + embeddings)
ollama pull llama3.2:3b
ollama pull nomic-embed-text

# Optional — only if MODEL_PROVIDER=ollama
ollama pull qwen3:8b
```

---

## Quick Start

### 1. Install Dependencies

```bash
cd d:\project\Strands
pip install -e .
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` and set your chosen model provider + keys:

| `MODEL_PROVIDER` | Required Key | Where to Get It |
|-------------------|-------------|-----------------|
| `groq` (default) | `GROQ_API_KEY` | <https://console.groq.com> (free tier) |
| `gemini` | `GEMINI_API_KEY` | <https://aistudio.google.com> (free, no card) |
| `ollama` | None | Just run `ollama serve` |

Also set `TAVILY_API_KEY` for web search — get a free key at <https://tavily.com> (1,000 searches/month).

### 3. Ensure Ollama Is Running

```bash
ollama serve
```

Memory depends on Ollama regardless of your chosen model provider.

### 4. Test Standalone (Optional)

```bash
python agent.py
```

This starts an interactive REPL. Type messages and verify the agent responds.

### 5. Run the MCP Server

#### stdio transport (local, for Claude Desktop/Code)

```bash
python server.py
```

#### streamable-http transport (remote/container)

```bash
set TRANSPORT=http
python server.py
# Server starts on http://0.0.0.0:8000
```

### 6. Test with MCP Inspector

```bash
npx @modelcontextprotocol/inspector python server.py
```

In the Inspector UI:
1. Call `ask_assistant` with `message: "What time is it?"`
2. Call `ask_assistant` with `message: "My favorite programming language is Python. Remember that."`
3. **Restart the server** (Ctrl+C, re-run)
4. Call `ask_assistant` with `message: "What's my favorite programming language?"`
   → Should recall "Python" from memory
5. Call `ask_assistant` with `message: "Search the web for the latest AI agent news"`
   → Should return real results from Tavily

---

## Claude Desktop Configuration

Add to your `claude_desktop_config.json`:

**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "strands-assistant": {
      "command": "python",
      "args": ["d:\\project\\Strands\\server.py"],
      "env": {
        "MODEL_PROVIDER": "groq",
        "GROQ_API_KEY": "gsk_...",
        "TAVILY_API_KEY": "tvly-..."
      }
    }
  }
}
```

---

## Claude Code Configuration

```bash
claude mcp add strands-assistant python d:\project\Strands\server.py
```

Or add to `.claude/settings.json`:

```json
{
  "mcpServers": {
    "strands-assistant": {
      "command": "python",
      "args": ["d:\\project\\Strands\\server.py"]
    }
  }
}
```

---

## Docker Deployment

```bash
# Build
docker build -t strands-assistant .

# Run (streamable-http, default)
docker run --env-file .env \
  -p 8000:8000 \
  -v ./memory_db:/app/memory_db \
  -v ./notes:/app/notes \
  strands-assistant

# Connect MCP Inspector to the container
npx @modelcontextprotocol/inspector --url http://localhost:8000/mcp
```

> **Note:** The container defaults to `TRANSPORT=http`. For Ollama access from inside Docker, set `OLLAMA_HOST=http://host.docker.internal:11434` in your `.env`.

---

## Model Providers

### Groq (Default — Free Tier)

- Model: `openai/gpt-oss-120b` (117B MoE, strong tool-calling)
- Free tier at <https://console.groq.com>
- Set `GROQ_API_KEY` in `.env`

### Gemini (Free, No Card)

- Model: `gemini-2.5-flash`
- Free key at <https://aistudio.google.com>
- Set `GEMINI_API_KEY` in `.env`
- Daily quota varies — check current limits in AI Studio

### Ollama (Fully Local)

- Model: `qwen3:8b` (~8GB VRAM/RAM)
- No API key needed
- Run `ollama pull qwen3:8b` then `ollama serve`

### Memory (Configurable via `MEMORY_PROVIDER`)

Memory operations (fact extraction and embeddings) can run entirely in the cloud or locally, configurable via the `MEMORY_PROVIDER` env var in `.env`.

#### `MEMORY_PROVIDER=cloud` (Default)
- **LLM** (fact extraction): Groq `llama-3.1-8b-instant` (uses `GROQ_API_KEY`)
- **Embeddings**: Gemini `models/text-embedding-004` (uses `GEMINI_API_KEY`)
- **Vector store**: ChromaDB `PersistentClient` at `./memory_db/`

#### `MEMORY_PROVIDER=ollama` (Fully Local)
- **LLM** (fact extraction): `llama3.2:3b`
- **Embeddings**: `nomic-embed-text`
- **Vector store**: ChromaDB `PersistentClient` at `./memory_db/`
- Requires pulling models: `ollama pull llama3.2:3b` and `ollama pull nomic-embed-text`

---

## Architecture

```
MCP Client (Claude Desktop/Code/Inspector)
    │
    │ stdio or streamable-http
    ▼
server.py (FastMCP)
    │ ask_assistant tool
    ▼
agent.py (Strands Agent)
    ├── Model: Groq / Gemini / Ollama (configurable)
    ├── current_time
    ├── tavily_search (web)
    ├── remember / recall / list_memories (Mem0 + ChromaDB)
    ├── [Phase 2] MCPClient → Google Calendar
    ├── [Phase 3] MCPClient → Gmail (read-only)
    └── [Phase 4] file_read / file_write → ./notes/
```

---

## Project Structure

```
Strands/
├── agent.py           # Strands Agent: model factory + tools
├── server.py          # FastMCP server wrapping the agent
├── pyproject.toml     # Dependencies
├── Dockerfile         # Container build
├── README.md          # This file
├── .env.example       # Template for secrets
├── .gitignore
├── memory_db/         # ChromaDB storage (auto-created, gitignored)
└── notes/             # Phase 4: markdown notes
    └── .gitkeep
```

---

## Phase 2 — Google Calendar (Coming Next)

> Requires Google Cloud OAuth setup. Full walkthrough will be added here when Phase 2 is implemented.

## Phase 3 — Gmail Read-Only (Coming Next)

> Read/search only. Send capability disabled by default for safety.
> Requires `gmail.readonly` OAuth scope.
> Instructions for widening scope to allow sending will be documented here.

---

## Safety

- `BYPASS_TOOL_CONSENT` is **not set** — the agent will prompt for confirmation on writes/sends/deletes
- Real credentials are never committed — use `.env` (gitignored) with `.env.example` as template
- Memory data stays local in `./memory_db/` (ChromaDB) — no data sent to external memory services
- Gmail configured read-only by default (Phase 3)

---

## Troubleshooting

### "Ollama connection refused"
Ensure Ollama is running: `ollama serve`

### Memory not persisting
- Check that `./memory_db/` directory exists and is writable
- Verify Ollama models are pulled: `ollama list` should show `llama3.2:3b` and `nomic-embed-text`

### "GROQ_API_KEY not set"
Copy `.env.example` to `.env` and fill in your key, or switch `MODEL_PROVIDER` to `ollama`

### MCP Inspector not connecting
- For stdio: `npx @modelcontextprotocol/inspector python server.py`
- For HTTP: ensure `TRANSPORT=http` is set, then `npx @modelcontextprotocol/inspector --url http://localhost:8000/mcp`

### Docker can't reach Ollama
Add `OLLAMA_HOST=http://host.docker.internal:11434` to your `.env` when running in Docker
