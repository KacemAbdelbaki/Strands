"""Test doubles that let a real Strands Agent run with no API calls."""

import json
from collections.abc import AsyncIterator
from typing import Any

from strands.models.model import Model


def tool_call(name: str, tool_input: dict[str, Any] | None = None, tool_use_id: str | None = None) -> dict[str, Any]:
    """One scripted model turn that calls a tool."""
    return {"tool": name, "input": tool_input or {}, "id": tool_use_id or f"call-{name}"}


class ScriptedModel(Model):
    """A model that replies with a fixed script of turns, in order.

    Each turn is either a string (a text reply that ends the agent loop) or a `tool_call(...)`.
    Every request it receives is kept in `requests`, so tests can check what the model was shown.
    """

    def __init__(self, turns: list[str | dict[str, Any]] | None = None) -> None:
        self.turns = list(turns or [])
        self.requests: list[dict[str, Any]] = []
        self.config: dict[str, Any] = {"model_id": "scripted"}

    def update_config(self, **model_config: Any) -> None:
        self.config.update(model_config)

    def get_config(self) -> dict[str, Any]:
        return self.config

    async def structured_output(self, output_model, prompt, system_prompt=None, **kwargs):  # type: ignore[override]
        raise NotImplementedError("ScriptedModel has no structured output")
        yield  # pragma: no cover

    async def stream(  # type: ignore[override]
        self, messages, tool_specs=None, system_prompt=None, **kwargs: Any
    ) -> AsyncIterator[dict[str, Any]]:
        self.requests.append(
            {
                "messages": json.loads(json.dumps(messages, default=str)),
                "tool_names": [spec["name"] for spec in tool_specs or []],
                "system_prompt": system_prompt,
            }
        )
        turn = self.turns.pop(0) if self.turns else "done"

        yield {"messageStart": {"role": "assistant"}}
        if isinstance(turn, str):
            yield {"contentBlockDelta": {"delta": {"text": turn}}}
            yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "end_turn"}}
        else:
            yield {"contentBlockStart": {"start": {"toolUse": {"toolUseId": turn["id"], "name": turn["tool"]}}}}
            yield {"contentBlockDelta": {"delta": {"toolUse": {"input": json.dumps(turn["input"])}}}}
            yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "tool_use"}}


def tool_results(messages) -> list[str]:
    """The text of every tool result in a conversation, in order."""
    results = []
    for message in messages:
        for block in message["content"]:
            if "toolResult" in block:
                parts = block["toolResult"]["content"]
                results.append(" ".join(part.get("text", "") or json.dumps(part.get("json", "")) for part in parts))
    return results
