"""Hard limits on tool calls, enforced with Cedar before the approval prompt.

An approval prompt relies on the user noticing a bad call. A policy is a rule the model can't talk
its way around. Register it before the approval gate: interventions run in order and stop on a Deny,
so a forbidden call is refused without ever asking the user.
"""

import re
from pathlib import Path
from typing import Any

from strands.vended_interventions.cedar import CedarAuthorization

POLICY_FILE = Path(__file__).with_name("tools.cedar")


def _normalized_command(tool_name: str, tool_input: dict[str, Any]) -> str:
    """The terminal_exec command, lower-cased with whitespace collapsed; empty for other tools."""
    if tool_name != "terminal_exec":
        return ""
    command = tool_input.get("command", "")
    return re.sub(r"\s+", " ", str(command)).strip().lower()


def tool_policy(cloud_mode: bool) -> CedarAuthorization:
    """Build the Cedar policy check.

    Args:
        cloud_mode: True on the server, where the shell is forbidden outright.
    """

    def add_session_fields(call: dict[str, Any]) -> dict[str, Any]:
        # Every field a policy reads must always be present: in Cedar a policy that hits a missing
        # attribute errors and is skipped, which would make a forbid rule fail open.
        return {
            "cloud_mode": cloud_mode,
            "command": _normalized_command(call["tool_name"], call["tool_input"]),
        }

    return CedarAuthorization(
        policies=POLICY_FILE.read_text(encoding="utf-8"),
        context_enricher=add_session_fields,
        principal={"type": "User", "id": "owner"},
    )
