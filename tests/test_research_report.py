"""The Researcher returns a typed report, so "every claim has a source" is enforced, not just asked for."""

import json

import pytest
from pydantic import ValidationError

from fakes import ScriptedModel, tool_call
from strands_assistant import agent as agent_module
from strands_assistant.research import ResearchReport

VALID_REPORT = {
    "summary": "Acme released v2 on 3 March.",
    "findings": [
        {
            "claim": "Acme v2 shipped on 2026-03-03.",
            "sources": [{"title": "Acme v2 release notes", "reference": "https://acme.example/v2"}],
        }
    ],
    "assumptions": ["'latest release' means the latest stable release"],
    "injection_warnings": [],
}


@pytest.fixture
def scripted(monkeypatch):
    monkeypatch.delenv("CLOUD_MODE", raising=False)
    models: dict[str, ScriptedModel] = {}

    def fake_build_model(priority_env: str, default: str = "") -> ScriptedModel:
        return models.setdefault(priority_env, ScriptedModel())

    monkeypatch.setattr(agent_module, "build_model", fake_build_model)
    return models


def test_a_finding_without_a_source_is_rejected():
    report = {**VALID_REPORT, "findings": [{"claim": "Unsourced claim.", "sources": []}]}

    with pytest.raises(ValidationError):
        ResearchReport.model_validate(report)


def test_the_assistant_receives_the_report_as_json(scripted):
    scripted["RESEARCHER_MODEL_PRIORITY"] = ScriptedModel([tool_call("ResearchReport", VALID_REPORT)])
    scripted["MODEL_PRIORITY"] = ScriptedModel(
        [tool_call("research", {"input": "When did Acme ship v2?"}), "Acme shipped v2 on 3 March."]
    )

    assistant = agent_module.create_agent(ask=lambda prompt, **kw: "n")
    assistant("when did acme ship v2?")

    results = [
        block["toolResult"]
        for message in assistant.messages
        for block in message["content"]
        if "toolResult" in block
    ]
    report = ResearchReport.model_validate(results[-1]["content"][0]["json"])
    assert report.findings[0].sources[0].reference == "https://acme.example/v2"


def test_a_researcher_that_answers_in_prose_is_made_to_return_the_report(scripted):
    model = ScriptedModel(["Acme shipped v2 in March.", tool_call("ResearchReport", VALID_REPORT)])
    scripted["RESEARCHER_MODEL_PRIORITY"] = model

    result = agent_module.create_researcher()("When did Acme ship v2?")

    assert isinstance(result.structured_output, ResearchReport)
    assert json.loads(result.structured_output.model_dump_json())["summary"] == VALID_REPORT["summary"]
