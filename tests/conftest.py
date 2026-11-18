import pytest

from strands_assistant import agent as agent_module
from strands_assistant import settings


@pytest.fixture(autouse=True)
def isolated_agent_state(monkeypatch, tmp_path):
    """Keep memory and chat history written by tests out of the real data folder."""
    state_dir = tmp_path / "agent_state"
    monkeypatch.setattr(settings, "AGENT_STATE_DIR", state_dir)
    return state_dir


@pytest.fixture(autouse=True)
def no_real_aux_model(monkeypatch):
    """agent.py loads .env, so a real side-job model could call a live API. Tests opt in to a fake."""
    monkeypatch.setattr(agent_module, "build_single_model", lambda priority_env, default="": None)
