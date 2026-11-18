"""The Assistant keeps its conversation across restarts, and summarizes instead of overflowing."""

import pytest

from fakes import ScriptedModel
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
    raise AssertionError(f"unexpected approval prompt: {prompt}")


def test_the_conversation_survives_a_restart(scripted):
    scripted["MODEL_PRIORITY"] = ScriptedModel(["Noted."])
    agent_module.create_agent(ask=_no_prompts)("My favourite colour is teal.")

    model = ScriptedModel(["You said your favourite colour is teal."])
    scripted["MODEL_PRIORITY"] = model
    agent_module.create_agent(ask=_no_prompts)("What did I just say?")

    assert "favourite colour is teal" in str(model.requests[0]["messages"])


def test_a_long_chat_is_summarized_instead_of_failing(scripted):
    model = ScriptedModel()
    scripted["MODEL_PRIORITY"] = model
    agent = agent_module.create_agent(ask=_no_prompts)
    for turn in range(15):
        agent(f"message number {turn}")
    before = len(agent.messages)

    model.max_messages = 12
    # Replies to the summarization requests (and the final answer); a trimming manager never asks
    model.turns = ["Summary: the user sent numbered messages starting from 0."] * 5
    agent("one more message")

    assert len(agent.messages) < before
    assert "Summary: the user sent numbered messages" in str(agent.messages[0])
    assert len(model.requests[-1]["messages"]) <= 12
