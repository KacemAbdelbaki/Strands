"""The terminal chat loop: memory extraction keeps its every-few-turns cadence, and errors don't end the chat."""

import pytest

from fakes import ScriptedModel
from strands_assistant import agent as agent_module


@pytest.fixture
def scripted(monkeypatch):
    monkeypatch.delenv("CLOUD_MODE", raising=False)
    models: dict[str, ScriptedModel] = {}

    def fake_build_model(priority_env: str, default: str = "") -> ScriptedModel:
        return models.setdefault(priority_env, ScriptedModel())

    monkeypatch.setattr(agent_module, "build_model", fake_build_model)
    return models


def _lines(*lines):
    """Stands in for input(): returns each line, then behaves like Ctrl+D."""
    remaining = list(lines)

    def read_line(prompt: str = "") -> str:
        if not remaining:
            raise EOFError
        return remaining.pop(0)

    return read_line


def _extraction_requests(model: ScriptedModel) -> list:
    return [r for r in model.requests if "extract durable facts" in (r["system_prompt"] or "")]


def test_memory_extraction_does_not_run_on_every_turn(scripted, capsys):
    model = ScriptedModel(["one", "two"])
    scripted["MODEL_PRIORITY"] = model
    agent = agent_module.create_agent(ask=lambda prompt, **kw: "n")

    agent_module.run_chat(agent, read_line=_lines("I like ramen", "I live in Lyon"))

    chat_requests = [r for r in model.requests if r not in _extraction_requests(model)]
    assert len(chat_requests) == 2
    assert len(_extraction_requests(model)) == 1  # once, on exit, for the turns not yet saved


def test_a_failed_turn_does_not_end_the_chat(scripted, capsys):
    class FailsOnce(ScriptedModel):
        async def stream(self, messages, tool_specs=None, system_prompt=None, **kwargs):
            if not self.requests:
                self.requests.append({"messages": [], "tool_names": [], "system_prompt": system_prompt})
                raise RuntimeError("provider down")
            async for event in super().stream(messages, tool_specs, system_prompt, **kwargs):
                yield event

    scripted["MODEL_PRIORITY"] = FailsOnce(["second answer"])
    agent = agent_module.create_agent(ask=lambda prompt, **kw: "n")

    agent_module.run_chat(agent, read_line=_lines("first", "second"))

    output = capsys.readouterr().out
    assert "provider down" in output
    assert "second answer" in output
    assert "Goodbye" in output
