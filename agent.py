"""
Strands Personal Assistant — Agent Factory

Builds a Strands Agent with:
- Configurable model provider (Groq / Gemini / Ollama) via MODEL_PROVIDER env var
- Persistent memory via Mem0 (always local: Ollama + ChromaDB)
- Web search via Tavily
- Current time tool
"""

import logging
import os
from dotenv import load_dotenv
from strands import Agent

# Import modular components
from logic.models import _build_model
from prompts import SYSTEM_PROMPT
from tools.memory_tools import remember, recall, list_memories
from tools.notes_tools import take_note, get_notes
from tools.system_tools import terminal_exec, take_screenshot
from tools.email_tools import get_emails

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Agent factory
# ---------------------------------------------------------------------------

def create_agent() -> Agent:
    """Build and return the configured Strands Agent."""
    from strands_tools import current_time
    from strands_tools.tavily import tavily_search

    model = _build_model()

    agent = Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=[
            current_time,
            tavily_search,
            remember,
            recall,
            list_memories,
            take_note,
            get_notes,
            terminal_exec,
            take_screenshot,
            get_emails,
        ],
    )

    logger.info(
        "Agent created with MODEL_PROVIDER=%s",
        os.getenv("MODEL_PROVIDER", "groq"),
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
