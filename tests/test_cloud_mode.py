"""CLOUD_MODE must remove the shell from the agent entirely, not just block it."""

import pytest

from strands_assistant.agent import create_agent


@pytest.fixture(autouse=True)
def offline_models(monkeypatch):
    """Building an agent makes no API calls, but the model builders need a key to exist."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("MODEL_PRIORITY", "gemini")
    monkeypatch.setenv("RESEARCHER_MODEL_PRIORITY", "gemini")


def test_cloud_mode_leaves_terminal_exec_out_of_the_agent(monkeypatch):
    monkeypatch.setenv("CLOUD_MODE", "true")

    assert "terminal_exec" not in create_agent().tool_names


def test_cloud_mode_prompt_does_not_offer_a_shell(monkeypatch):
    monkeypatch.setenv("CLOUD_MODE", "true")

    assert "terminal_exec" not in create_agent().system_prompt


def test_pc_mode_keeps_terminal_exec(monkeypatch):
    monkeypatch.delenv("CLOUD_MODE", raising=False)

    agent = create_agent()

    assert "terminal_exec" in agent.tool_names
    assert "terminal_exec" in agent.system_prompt
