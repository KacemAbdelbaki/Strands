"""
Strands Personal Assistant — Agent Factory

Two agents, wired with the "agents as tools" pattern:
- Assistant (user-facing orchestrator): long-term memory (MemoryManager), notes, calendar, terminal, time,
  plus the Researcher exposed as the `research` tool. With CLOUD_MODE=true it has
  no terminal, because on a server it would run next to the Google tokens and API keys.
  Model chain: MODEL_PRIORITY (default gemini,groq,ollama).
- Researcher (read-only): web search (Tavily) + Gmail. Starts fresh on every call
  and never sees the user conversation, so untrusted email/web content stays away
  from the agent that can run shell commands.
  Model chain: RESEARCHER_MODEL_PRIORITY (default groq,gemini,ollama).
"""

import logging
import os
from copy import deepcopy
from typing import Any

from dotenv import load_dotenv
from strands import Agent, ModelRetryStrategy
from strands.agent.conversation_manager import SummarizingConversationManager
from strands.session import FileSessionManager
from strands.vended_plugins.context_offloader import ContextOffloader, InMemoryStorage
from strands.vended_tools.notebook import make_notebook
from strands.hooks.events import BeforeInvocationEvent

load_dotenv()

# Import modular components
from strands_assistant.approvals import approval_gate
from strands_assistant.logic.models import build_model
from strands_assistant.policies import tool_policy
from strands_assistant.prompts import (
    CLOUD_SYSTEM_PROMPT,
    RESEARCH_TOOL_DESCRIPTION,
    RESEARCHER_PROMPT,
    SYSTEM_PROMPT,
)
from strands_assistant import settings
from strands_assistant.memory import create_memory_manager
from strands_assistant.settings import is_cloud_mode
from strands_assistant.tools.email_tools import get_emails
from strands_assistant.tools.calendar_tools import get_events, create_event

logger = logging.getLogger(__name__)

# Groq's free tier allows about 8,000 tokens a minute for gpt-oss-20b, and one research run makes
# several calls, so a single tool result must stay well under that.
RESEARCHER_MAX_RESULT_TOKENS = 1_500
RESEARCHER_PREVIEW_TOKENS = 500

# One user, one ongoing conversation. The web UI can pass its own ids later.
SESSION_ID = "default"

# gpt-oss reasoning warning supression
logging.getLogger("strands.models.openai").setLevel(logging.ERROR)


def _strip_reasoning_content(value):
    if isinstance(value, dict):
        return {
            key: _strip_reasoning_content(item)
            for key, item in value.items()
            if key not in {"reasoningContent", "reasoning_content"}
        }
    if isinstance(value, list):
        return [_strip_reasoning_content(item) for item in value]
    return value


def sanitize_history(event: BeforeInvocationEvent) -> None:
    """Remove provider-specific reasoning blocks before a fallback model sees history."""
    if event.messages is not None:
        event.messages = _strip_reasoning_content(deepcopy(event.messages))

# ---------------------------------------------------------------------------
# Agent factory
# ---------------------------------------------------------------------------

def main() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "WARNING").upper(),
        format="%(levelname)s: %(message)s",
    )
    agent = create_agent()
    print("Agent ready. Type a message (Ctrl+C to quit):\n")
    while True:
        try:
            user_input = input("You: ")
            if not user_input.strip():
                continue
            print("\nAssistant: ", end="", flush=True)
            agent(user_input)
            print("\n")
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            return
        except Exception as error:
            logger.exception("Agent turn failed")
            print(f"\nAssistant error: {error}\n")


def create_researcher() -> Agent:
    """Build the read-only Researcher agent (web search + Gmail, no local side effects)."""
    from strands_tools import current_time
    from strands_tools.tavily import tavily_search

    model = build_model("RESEARCHER_MODEL_PRIORITY", "groq,gemini,ollama")

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
        hooks=[sanitize_history],
        plugins=[
            # Large results are the main cause of Groq's free-tier tokens-per-minute failures. Anything
            # over the limit is replaced by a preview, and the Researcher can fetch the rest with
            # retrieve_offloaded_content. Kept in memory, not on disk, because it holds email content.
            ContextOffloader(
                storage=InMemoryStorage(),
                max_result_tokens=RESEARCHER_MAX_RESULT_TOKENS,
                preview_tokens=RESEARCHER_PREVIEW_TOKENS,
            )
        ],
        callback_handler=None,
    )


def create_agent(ask: Any = "stdio") -> Agent:
    """Build and return the user-facing Assistant, with the Researcher as its `research` tool.

    Args:
        ask: How tool approvals are collected: "stdio" prompts in the terminal, a callable answers
            them, and None pauses the agent with an interrupt (see `approvals.approval_gate`).
    """
    from strands_tools import current_time

    # MODEL_PROVIDER kept for single-model backwards compatibility
    model = build_model("MODEL_PRIORITY", os.getenv("MODEL_PROVIDER", "gemini,groq,ollama"))

    # preserve_context=False (the default) resets the Researcher before every call
    research = create_researcher().as_tool(name="research", description=RESEARCH_TOOL_DESCRIPTION)

    tools = [
        current_time,
        research,
        # Notes live in agent.state, so the session manager below is what keeps them
        make_notebook(),
        get_events,
        create_event,
    ]
    cloud = is_cloud_mode()
    if not cloud:
        from strands_assistant.tools.system_tools import terminal_exec

        tools.append(terminal_exec)

    agent = Agent(
        model=model,
        system_prompt=CLOUD_SYSTEM_PROMPT if cloud else SYSTEM_PROMPT,
        tools=tools,
        retry_strategy=ModelRetryStrategy(
            max_attempts=3,
            initial_delay=2,
            max_delay=60,
        ),
        hooks=[sanitize_history],
        # Chat history survives restarts. Only the Assistant has one: as_tool rejects a session
        # manager on the Researcher, which starts fresh on every call anyway.
        session_manager=FileSessionManager(session_id=SESSION_ID, storage_dir=str(settings.AGENT_STATE_DIR / "sessions")),
        # When the context overflows, older turns are summarized instead of dropped
        conversation_manager=SummarizingConversationManager(),
        # Adds search_memory, add_memory and list_memories, and injects relevant memories each turn
        memory_manager=create_memory_manager(settings.AGENT_STATE_DIR),
        # Order matters: the Cedar policy refuses forbidden calls before the user is ever asked
        interventions=[tool_policy(cloud_mode=cloud), approval_gate(ask)],
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
    main()
