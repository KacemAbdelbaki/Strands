"""
Strands Personal Assistant — Agent Factory

Two agents, wired with the "agents as tools" pattern:
- Assistant (user-facing orchestrator): memory, notes, calendar, terminal, time,
  plus the Researcher exposed as the `research` tool.
  Model chain: MODEL_PRIORITY (default gemini,groq,ollama).
- Researcher (read-only): web search (Tavily) + Gmail. Starts fresh on every call
  and never sees the user conversation, so untrusted email/web content stays away
  from the agent that can run shell commands.
  Model chain: RESEARCHER_MODEL_PRIORITY (default groq,gemini,ollama).
"""

import logging
import os
from dotenv import load_dotenv
from strands import Agent, ModelRetryStrategy

# Import modular components
from logic.models import _build_model
from prompts import RESEARCH_TOOL_DESCRIPTION, RESEARCHER_PROMPT, SYSTEM_PROMPT
from tools.memory_tools import remember, recall, list_memories
from tools.notes_tools import take_note, get_notes
from tools.system_tools import terminal_exec
from tools.email_tools import get_emails
from tools.calendar_tools import get_events, create_event

load_dotenv()

logger = logging.getLogger(__name__)

# gpt-oss reasoning warning supression
logging.getLogger("strands.models.openai").setLevel(logging.ERROR)

# ---------------------------------------------------------------------------
# Agent factory
# ---------------------------------------------------------------------------


def create_researcher() -> Agent:
    """Build the read-only Researcher agent (web search + Gmail, no local side effects)."""
    from strands_tools import current_time
    from strands_tools.tavily import tavily_search

    model = _build_model("RESEARCHER_MODEL_PRIORITY", "groq,gemini,ollama")

    return Agent(
        name="researcher",
        model=model,
        system_prompt=RESEARCHER_PROMPT,
        tools=[tavily_search, get_emails, current_time],
        retry_strategy=ModelRetryStrategy(
            max_attempts=3,
            initial_delay=2,
            max_delay=60,
        ),
        callback_handler=None,
    )


def create_agent() -> Agent:
    """Build and return the user-facing Assistant, with the Researcher as its `research` tool."""
    from strands_tools import current_time

    # MODEL_PROVIDER kept for single-model backwards compatibility
    model = _build_model("MODEL_PRIORITY", os.getenv("MODEL_PROVIDER", "gemini,groq,ollama"))

    # preserve_context=False (the default) resets the Researcher before every call
    research = create_researcher().as_tool(name="research", description=RESEARCH_TOOL_DESCRIPTION)

    agent = Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=[
            current_time,
            research,
            remember,
            recall,
            list_memories,
            take_note,
            get_notes,
            get_events,
            create_event,
            terminal_exec,
        ],
        retry_strategy=ModelRetryStrategy(
            max_attempts=3,
            initial_delay=2,
            max_delay=60,
        ),
    )

    logger.info(
        "Agents created: assistant MODEL_PRIORITY=%s, researcher RESEARCHER_MODEL_PRIORITY=%s",
        os.getenv("MODEL_PRIORITY", os.getenv("MODEL_PROVIDER", "gemini,groq,ollama")),
        os.getenv("RESEARCHER_MODEL_PRIORITY", "groq,gemini,ollama"),
    )
    return agent


# ---------------------------------------------------------------------------
# Standalone test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    agent = create_agent()
    print("Agent ready. Type a message (Ctrl+C to quit):\n")
    while True:
        try:
            user_input = input("You: ")
            if not user_input.strip():
                continue
            print("\nAssistant: ", end="", flush=True)
            response = agent(user_input)
            print("\n")
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
