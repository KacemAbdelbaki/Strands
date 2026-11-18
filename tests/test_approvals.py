"""Tool approvals go through the SDK's HumanInTheLoop gate, so a new tool is protected by default."""

import pytest
from strands import Agent, tool

from fakes import ScriptedModel, tool_call
from strands_assistant import agent as agent_module
from strands_assistant.approvals import approval_gate


class RecordingAsk:
    """Stands in for the person at the keyboard: answers every prompt the same way."""

    def __init__(self, answer: str) -> None:
        self.answer = answer
        self.prompts: list[str] = []

    def __call__(self, prompt: str, **kwargs) -> str:
        self.prompts.append(prompt)
        return self.answer


@pytest.fixture
def scripted(monkeypatch, tmp_path):
    """Make create_agent build its models from a script instead of real providers."""
    monkeypatch.setenv("STRANDS_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("CLOUD_MODE", raising=False)
    models: dict[str, ScriptedModel] = {}

    def fake_build_model(priority_env: str, default: str = "") -> ScriptedModel:
        return models.setdefault(priority_env, ScriptedModel())

    monkeypatch.setattr(agent_module, "build_model", fake_build_model)
    return models


def _write_file_command(path) -> str:
    return f'echo ran > "{path}"'


def test_declining_terminal_exec_cancels_the_command(scripted, tmp_path):
    marker = tmp_path / "ran.txt"
    scripted["MODEL_PRIORITY"] = ScriptedModel(
        [tool_call("terminal_exec", {"command": _write_file_command(marker)}), "ok"]
    )
    ask = RecordingAsk("n")

    agent_module.create_agent(ask=ask)("run it")

    assert len(ask.prompts) == 1
    assert "terminal_exec" in ask.prompts[0]
    assert not marker.exists()


def test_approving_terminal_exec_runs_the_command_once(scripted, tmp_path):
    marker = tmp_path / "ran.txt"
    scripted["MODEL_PRIORITY"] = ScriptedModel(
        [tool_call("terminal_exec", {"command": _write_file_command(marker)}), "ok"]
    )
    ask = RecordingAsk("y")

    agent_module.create_agent(ask=ask)("run it")

    assert len(ask.prompts) == 1
    assert marker.exists()


def test_create_event_needs_approval(scripted):
    scripted["MODEL_PRIORITY"] = ScriptedModel(
        [tool_call("create_event", {"summary": "Dentist", "start": "2026-12-01", "end": "2026-12-02"}), "ok"]
    )
    ask = RecordingAsk("n")

    agent_module.create_agent(ask=ask)("book it")

    assert len(ask.prompts) == 1
    assert "create_event" in ask.prompts[0]


def test_read_only_tools_run_without_a_prompt(scripted):
    scripted["MODEL_PRIORITY"] = ScriptedModel([tool_call("current_time", {"timezone": "UTC"}), "ok"])
    ask = RecordingAsk("n")

    agent_module.create_agent(ask=ask)("what time is it?")

    assert ask.prompts == []


def test_a_new_unlisted_tool_needs_approval_by_default():
    calls = []

    @tool
    def brand_new_tool() -> str:
        """A tool nobody added to the allow-list."""
        calls.append(1)
        return "done"

    ask = RecordingAsk("n")
    agent = Agent(
        model=ScriptedModel([tool_call("brand_new_tool"), "ok"]),
        tools=[brand_new_tool],
        interventions=[approval_gate(ask)],
        callback_handler=None,
    )

    agent("go")

    assert len(ask.prompts) == 1
    assert calls == []
