"""Notes use the SDK's notebook tool, kept in the agent's session."""

import pytest

from fakes import ScriptedModel, tool_call, tool_results
from strands_assistant import agent as agent_module


@pytest.fixture
def scripted(monkeypatch):
    """Make create_agent build its models from a script instead of real providers."""
    monkeypatch.delenv("CLOUD_MODE", raising=False)
    models: dict[str, ScriptedModel] = {}

    def fake_build_model(priority_env: str, default: str = "") -> ScriptedModel:
        return models.setdefault(priority_env, ScriptedModel())

    monkeypatch.setattr(agent_module, "build_model", fake_build_model)
    return models


def _no_prompts(prompt, **kwargs):
    raise AssertionError(f"note-taking should not need approval, but got: {prompt}")


def test_notes_use_the_builtin_notebook(scripted):
    names = set(agent_module.create_agent(ask=_no_prompts).tool_names)

    assert "notebook" in names
    assert not {"take_note", "get_notes"} & names


def test_a_note_survives_a_restart(scripted):
    scripted["MODEL_PRIORITY"] = ScriptedModel(
        [tool_call("notebook", {"mode": "write", "new_str": "Buy oat milk"}), "Noted."]
    )
    agent_module.create_agent(ask=_no_prompts)("note: buy oat milk")

    scripted["MODEL_PRIORITY"] = ScriptedModel([tool_call("notebook", {"mode": "read"}), "ok"])
    restarted = agent_module.create_agent(ask=_no_prompts)
    restarted("what's in my notes?")

    assert "Buy oat milk" in tool_results(restarted.messages)[-1]
