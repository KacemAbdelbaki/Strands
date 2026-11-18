"""Memory uses the SDK's MemoryManager with a file store, and survives restarts."""

import asyncio
import sqlite3

import pytest

from fakes import ScriptedModel, tool_call, tool_results
from strands_assistant import agent as agent_module
from strands_assistant import settings
from strands_assistant.memory import create_memory_store
from strands_assistant.migrate_memory import migrate, read_mem0_memories


@pytest.fixture
def scripted(monkeypatch):
    """Make create_agent build its models from a script instead of real providers."""
    monkeypatch.delenv("CLOUD_MODE", raising=False)
    models: dict[str, ScriptedModel] = {}

    def fake_build_model(priority_env: str, default: str = "") -> ScriptedModel:
        return models.setdefault(priority_env, ScriptedModel())

    monkeypatch.setattr(agent_module, "build_model", fake_build_model)
    return models


def _never_asked(prompt, **kwargs):
    raise AssertionError(f"memory tools should not need approval, but got: {prompt}")


def test_no_tool_lets_the_model_pick_whose_memory_to_read(scripted):
    agent = agent_module.create_agent(ask=_never_asked)

    for spec in agent.tool_registry.get_all_tool_specs():
        properties = spec["inputSchema"]["json"].get("properties", {})
        assert "user_id" not in properties, spec["name"]


def test_memory_tools_are_the_sdk_ones(scripted):
    names = agent_module.create_agent(ask=_never_asked).tool_names

    assert {"search_memory", "add_memory", "list_memories"} <= set(names)
    assert not {"remember", "recall"} & set(names)


def test_memories_survive_a_restart(scripted):
    scripted["MODEL_PRIORITY"] = ScriptedModel(
        [tool_call("add_memory", {"entries": ["# Work\nThe user's employer is Acme Robotics."]}), "saved"]
    )
    agent_module.create_agent(ask=_never_asked)("remember where I work")

    scripted["MODEL_PRIORITY"] = ScriptedModel([tool_call("search_memory", {"query": "employer"}), "ok"])
    restarted = agent_module.create_agent(ask=_never_asked)
    restarted("who is my employer?")

    assert "Acme Robotics" in tool_results(restarted.messages)[-1]


def test_relevant_memories_reach_the_model_without_a_tool_call(scripted):
    scripted["MODEL_PRIORITY"] = ScriptedModel(
        [tool_call("add_memory", {"entries": ["# Work\nThe user's employer is Acme Robotics."]}), "saved"]
    )
    agent_module.create_agent(ask=_never_asked)("remember where I work")

    model = ScriptedModel(["You work at Acme Robotics."])
    scripted["MODEL_PRIORITY"] = model
    agent_module.create_agent(ask=_never_asked)("who is my employer?")

    assert "Acme Robotics" in str(model.requests[0]["messages"])


def test_list_memories_shows_everything_stored(scripted):
    scripted["MODEL_PRIORITY"] = ScriptedModel(
        [
            tool_call("add_memory", {"entries": ["# Work\nEmployer is Acme.", "# Food\nLikes ramen."]}),
            tool_call("list_memories", tool_use_id="list-1"),
            "ok",
        ]
    )
    agent = agent_module.create_agent(ask=_never_asked)
    agent("remember these, then show me everything")

    listing = tool_results(agent.messages)[-1]
    assert "Acme" in listing
    assert "ramen" in listing


def _make_mem0_chroma_db(path, rows):
    """A minimal copy of the Chroma tables that hold Mem0's memory text."""
    db = sqlite3.connect(path)
    db.executescript(
        """
        CREATE TABLE collections (id TEXT PRIMARY KEY, name TEXT);
        CREATE TABLE segments (id TEXT PRIMARY KEY, collection TEXT);
        CREATE TABLE embeddings (id INTEGER PRIMARY KEY, segment_id TEXT, embedding_id TEXT);
        CREATE TABLE embedding_metadata (id INTEGER, key TEXT, string_value TEXT);
        INSERT INTO collections VALUES ('c1', 'assistant_memory'), ('c2', 'mem0migrations');
        INSERT INTO segments VALUES ('s1', 'c1'), ('s2', 'c2');
        """
    )
    for row_id, (collection_segment, key, value) in enumerate(rows, 1):
        db.execute("INSERT INTO embeddings VALUES (?, ?, ?)", (row_id, collection_segment, f"e{row_id}"))
        db.execute("INSERT INTO embedding_metadata VALUES (?, ?, ?)", (row_id, key, value))
    db.commit()
    db.close()


def test_migration_reads_only_mem0_memory_text(tmp_path):
    db_path = tmp_path / "chroma.sqlite3"
    _make_mem0_chroma_db(
        db_path,
        [
            ("s1", "data", "Employer is Acme Robotics"),
            ("s1", "data", "Prefers dark mode"),
            ("s1", "hash", "abc123"),
            ("s2", "data", "internal mem0 migration record"),
        ],
    )

    assert read_mem0_memories(db_path) == ["Employer is Acme Robotics", "Prefers dark mode"]


def test_migrated_facts_can_be_found(tmp_path):
    db_path = tmp_path / "chroma.sqlite3"
    _make_mem0_chroma_db(db_path, [("s1", "data", "Employer is Acme Robotics")])
    store = create_memory_store(settings.AGENT_STATE_DIR)

    count = asyncio.run(migrate(db_path, store))

    assert count == 1
    found = asyncio.run(store.search("employer"))
    assert any("Acme Robotics" in entry.content for entry in found)


def test_migration_can_run_twice_without_duplicating(tmp_path):
    db_path = tmp_path / "chroma.sqlite3"
    _make_mem0_chroma_db(db_path, [("s1", "data", "Employer is Acme Robotics")])
    store = create_memory_store(settings.AGENT_STATE_DIR)

    asyncio.run(migrate(db_path, store))
    asyncio.run(migrate(db_path, store))

    found = asyncio.run(store.search("employer"))
    assert sum(entry.content.count("Acme Robotics") for entry in found) == 1
