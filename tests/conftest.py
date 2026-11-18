import pytest

from strands_assistant import settings


@pytest.fixture(autouse=True)
def isolated_agent_state(monkeypatch, tmp_path):
    """Keep memory and chat history written by tests out of the real data folder."""
    state_dir = tmp_path / "agent_state"
    monkeypatch.setattr(settings, "AGENT_STATE_DIR", state_dir)
    return state_dir
