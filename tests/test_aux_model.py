"""Side jobs (memory extraction, summaries, action checks) run on a separate small model."""

import pytest

from fakes import ScriptedModel
from strands_assistant import agent as agent_module
from strands_assistant.logic import models as models_module


@pytest.fixture
def fake_providers(monkeypatch):
    built = []

    def builder(name):
        def build():
            built.append(name)
            return ScriptedModel()

        return build

    def missing_key():
        raise RuntimeError("GROQ_API_KEY is not set")

    monkeypatch.setattr(
        models_module, "_BUILDERS", {"ollama": builder("ollama"), "groq": builder("groq"), "nokey": missing_key}
    )
    return built


def test_the_first_usable_provider_is_used(fake_providers, monkeypatch):
    monkeypatch.setattr(models_module, "_ollama_available", lambda: False)
    monkeypatch.setenv("AUX_MODEL_PRIORITY", "nokey,ollama,groq")

    model = models_module.build_single_model("AUX_MODEL_PRIORITY", "ollama,groq")

    assert isinstance(model, ScriptedModel)
    assert fake_providers == ["groq"]


def test_no_usable_provider_means_no_aux_model(fake_providers, monkeypatch):
    monkeypatch.setattr(models_module, "_ollama_available", lambda: False)
    monkeypatch.setenv("AUX_MODEL_PRIORITY", "nokey,ollama")

    assert models_module.build_single_model("AUX_MODEL_PRIORITY", "ollama,groq") is None


def _lines(*lines):
    remaining = list(lines)

    def read_line(prompt=""):
        if not remaining:
            raise EOFError
        return remaining.pop(0)

    return read_line


def test_memory_extraction_runs_on_the_aux_model(monkeypatch, capsys):
    monkeypatch.delenv("CLOUD_MODE", raising=False)
    main, aux = ScriptedModel(["hi"]), ScriptedModel(['[{"content": "# Food\\nLikes ramen"}]'])
    monkeypatch.setattr(agent_module, "build_model", lambda env, default="": main if env == "MODEL_PRIORITY" else ScriptedModel())
    monkeypatch.setattr(agent_module, "build_single_model", lambda env, default="": aux)

    agent = agent_module.create_agent(ask=lambda prompt, **kw: "n")
    agent_module.run_chat(agent, read_line=_lines("I like ramen"))

    assert agent.aux_model is aux
    assert len(main.requests) == 1  # only the chat turn
    assert any("extract durable facts" in (r["system_prompt"] or "") for r in aux.requests)
