"""Tool approvals through the SDK's HumanInTheLoop intervention.

Every tool needs approval unless it is listed here, so a tool added later is protected by default.
The gate runs before each tool call and serializes prompts, which matters because Strands runs
tool calls concurrently.
"""

from typing import Any, Literal

from strands.hooks.events import BeforeToolCallEvent
from strands.interventions.actions import InterventionAction, Proceed
from strands.vended_interventions.hitl import HumanInTheLoop

# Read-only or low-risk tools. Anything that changes the user's machine or accounts
# (terminal_exec, create_event) must stay off this list.
ALLOWED_TOOLS = [
    "current_time",
    "research",
    "search_memory",
    "add_memory",
    "list_memories",
    "notebook",
    "get_events",
]


class ApprovalGate(HumanInTheLoop):
    """HumanInTheLoop that doesn't ask about a call something earlier has already cancelled.

    Interventions run after ordinary hooks, so when the action check has cancelled a call, the stock
    handler would still ask the user to approve a call that can no longer run.
    """

    async def before_tool_call(self, event: BeforeToolCallEvent, **kwargs: Any) -> InterventionAction:
        if event.cancel_tool:
            return Proceed(reason="already cancelled")
        return await super().before_tool_call(event, **kwargs)


def approval_gate(ask: Any | Literal["stdio"] | None = "stdio") -> HumanInTheLoop:
    """Build the approval gate.

    Args:
        ask: "stdio" prompts in the terminal, a callable answers prompts (web UI, tests), and None
            pauses the agent with an interrupt so the caller can resume it with the answer.
    """
    return ApprovalGate(allowed_tools=ALLOWED_TOOLS, ask=ask)
