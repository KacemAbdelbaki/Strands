# Strands Personal Assistant

A personal assistant you chat with in the terminal, built with [Strands Agents](https://strandsagents.com) (Python).
It runs on free-tier models (Gemini, Groq) with a local Ollama fallback.

## What it can do

| Area | Tools |
|------|-------|
| Memory | `remember`, `recall`, `list_memories` (Mem0 + ChromaDB) |
| Notes | `take_note`, `get_notes` (saved to `notes/note.txt`) |
| Google Calendar | `get_events`, `create_event` |
| Terminal | `terminal_exec` (runs shell commands on your machine) |
| Research | `research`: a separate agent with web search (Tavily) and read-only Gmail |
| Time | `current_time` |

`create_event` and `terminal_exec` ask for confirmation (`[y/N]`) before they run.

## How it works

```
You (terminal)
  │
  ▼
Assistant agent    memory, notes, calendar, terminal, time
  │
  └── research ──► Researcher agent    web search, Gmail (read-only)
```

The Researcher starts fresh on every call and never sees your conversation. Email and web content stay
with an agent that cannot run commands; the Assistant only gets the Researcher's summary.

Each agent has a model fallback chain: if one provider fails or hits a rate limit, the next one takes over.

## Setup

### 1. Install

Requires Python 3.11+.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .
```

### 2. Create a `.env` file

```env
GEMINI_API_KEY=...        # https://aistudio.google.com (free)
GROQ_API_KEY=...          # https://console.groq.com (free tier)
TAVILY_API_KEY=...        # https://tavily.com (free tier, web search)
```

Optional settings:

| Variable | Default | Purpose |
|----------|---------|---------|
| `MODEL_PRIORITY` | `gemini,groq,ollama` | Assistant model fallback order |
| `RESEARCHER_MODEL_PRIORITY` | `groq,gemini,ollama` | Researcher model fallback order |
| `MEMORY_PROVIDER` | `cloud` | `cloud` (Gemini) or `ollama` (fully local) |
| `MEM0_API_KEY` | none | Use the hosted Mem0 platform instead of local ChromaDB |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server address |
| `TERMINAL_TIMEOUT` | `60` | Seconds before a terminal command is killed |
| `BYPASS_TOOL_CONSENT` | not set | Set to `true` to skip the confirmation prompts (not recommended) |

Providers with no API key are skipped. Ollama is optional: to use it, run `ollama serve` and
`ollama pull qwen3:8b`. For local memory you also need `llama3.2:3b` and `nomic-embed-text`.

### 3. Google sign-in (Gmail and Calendar)

1. In [Google Cloud Console](https://console.cloud.google.com), enable the **Gmail API** and the
   **Google Calendar API**. Each one must be enabled in the project that owns its credentials file.
2. Create an OAuth client of type **Desktop app**, download its JSON, and save it as:
   - `credentials/gmail_credentials.json` for Gmail
   - `credentials/calendar_credentials.json` for Calendar
3. If the app is in "Testing" mode, add your Google account as a test user on the OAuth consent screen.

The first time a Gmail or Calendar tool runs, a browser window opens so you can sign in. The resulting
tokens (`gmail_token.json`, `calendar_token.json`) are saved in `credentials/`. To sign in again, delete
the token file. The `credentials/` folder is gitignored.

## Run

```bash
python agent.py
```

Then type your message, for example "what's on my calendar this week?" Press Ctrl+C to quit.

## Project structure

```
Strands/
├── agent.py            # Builds the Assistant and Researcher agents, runs the chat loop
├── prompts.py          # System prompts
├── logic/
│   ├── models.py       # Model fallback chain (Gemini / Groq / Ollama)
│   ├── memory.py       # Mem0 setup
│   ├── gmail.py        # Gmail OAuth
│   └── gcalendar.py    # Calendar OAuth
├── tools/              # Tools the agents can call
├── credentials/        # OAuth client files and tokens (gitignored)
├── notes/              # Notes
└── memory_db/          # Local memory store (gitignored)
```

## Troubleshooting

- **"Google Calendar API has not been used in project …"**: the API isn't enabled in the project that
  owns `calendar_credentials.json`. Enable it in the project named in the error. Changes can take a few
  minutes to apply.
- **"Authorisation has expired or was revoked"**: delete the matching token in `credentials/` and run again.
  In "Testing" mode, Google expires sign-ins after 7 days.
- **"Connection refused"**: every cloud provider failed and Ollama isn't running. Check your API keys,
  or start `ollama serve`.

Known issues are tracked in `to_fix.md`.
