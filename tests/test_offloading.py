"""Large tool results are offloaded on the Researcher instead of filling its context."""

import pytest
from strands import tool

from fakes import ScriptedModel, research_report, tool_call
from strands_assistant import agent as agent_module

BIG_RESULT = "email body line with lots of words. " * 2_000  # roughly 18k tokens


@pytest.fixture
def scripted(monkeypatch):
    """Scripted models, and a get_emails that returns one huge result."""
    monkeypatch.delenv("CLOUD_MODE", raising=False)
    models: dict[str, ScriptedModel] = {}

    def fake_build_model(priority_env: str, default: str = "") -> ScriptedModel:
        return models.setdefault(priority_env, ScriptedModel())

    @tool
    def get_emails(query: str = "") -> str:
        """Fake mailbox search."""
        return BIG_RESULT

    monkeypatch.setattr(agent_module, "build_model", fake_build_model)
    monkeypatch.setattr(agent_module, "get_emails", get_emails)
    return models


def _tool_result_sizes(request) -> list[int]:
    sizes = []
    for message in request["messages"]:
        for block in message["content"]:
            if "toolResult" in block:
                sizes.append(len(str(block["toolResult"]["content"])))
    return sizes


def test_a_huge_result_reaches_the_researcher_model_as_a_short_preview(scripted):
    model = ScriptedModel([tool_call("get_emails", {"query": "in:inbox"}), research_report()])
    scripted["RESEARCHER_MODEL_PRIORITY"] = model

    agent_module.create_researcher()("summarize my inbox")

    sizes = _tool_result_sizes(model.requests[1])
    assert sizes and max(sizes) < len(BIG_RESULT) / 5


def test_offloading_still_works_on_the_second_research_call(scripted):
    researcher_model = ScriptedModel(
        [
            tool_call("get_emails", {"query": "a"}, tool_use_id="r1"),
            research_report("first summary"),
            tool_call("get_emails", {"query": "b"}, tool_use_id="r2"),
            research_report("second summary"),
        ]
    )
    scripted["RESEARCHER_MODEL_PRIORITY"] = researcher_model
    scripted["MODEL_PRIORITY"] = ScriptedModel(
        [
            tool_call("research", {"input": "brief one"}, tool_use_id="a1"),
            tool_call("research", {"input": "brief two"}, tool_use_id="a2"),
            "done",
        ]
    )

    agent_module.create_agent(ask=lambda prompt, **kw: "n")("research twice")

    second_call_after_tool = researcher_model.requests[3]
    assert "brief one" not in str(second_call_after_tool["messages"])  # as_tool reset the Researcher
    sizes = _tool_result_sizes(second_call_after_tool)
    assert sizes and max(sizes) < len(BIG_RESULT) / 5
