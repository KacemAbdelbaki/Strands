"""Cedar policies refuse some tool calls outright, before the approval prompt is ever shown."""

import pytest
from strands import Agent, tool

from fakes import ScriptedModel, tool_call
from strands_assistant.approvals import approval_gate
from strands_assistant.policies import tool_policy


class RecordingAsk:
    """Answers "n" to every prompt, so even a broken policy can never run a command in these tests."""

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def __call__(self, prompt: str, **kwargs) -> str:
        self.prompts.append(prompt)
        return "n"


def _run(command: str, *, cloud_mode: bool = False) -> tuple[list[str], list[str]]:
    """Ask a guarded agent to run `command`; return the prompts shown and the commands that ran."""
    ran: list[str] = []

    @tool
    def terminal_exec(command: str) -> str:
        """Stand-in for the real shell tool."""
        ran.append(command)
        return "ok"

    ask = RecordingAsk()
    agent = Agent(
        model=ScriptedModel([tool_call("terminal_exec", {"command": command}), "ok"]),
        tools=[terminal_exec],
        interventions=[tool_policy(cloud_mode=cloud_mode), approval_gate(ask)],
        callback_handler=None,
    )
    agent("go")
    return ask.prompts, ran


def _last_tool_result(agent_messages) -> str:
    for message in reversed(agent_messages):
        for block in message["content"]:
            if "toolResult" in block:
                return " ".join(part.get("text", "") for part in block["toolResult"]["content"])
    raise AssertionError("no tool result found")


@pytest.mark.parametrize(
    "command",
    [
        "rm -rf ~/projects",
        "Remove-Item C:\\Users\\me -Recurse -Force",
        "remove-item  -recurse  C:\\data",
        "rd /s /q C:\\data",
        "del /s /q *.*",
        "format D:",
        "Format-Volume -DriveLetter D",
        "shutdown /s /t 0",
        "Stop-Computer",
        "diskpart",
        "reg delete HKLM\\Software\\X /f",
    ],
)
def test_destructive_commands_are_refused_without_a_prompt(command):
    prompts, ran = _run(command)

    assert prompts == []
    assert ran == []


def test_ordinary_commands_still_reach_the_approval_prompt():
    prompts, ran = _run("Get-ChildItem")

    assert len(prompts) == 1
    assert ran == []  # RecordingAsk declined it


def test_cloud_mode_refuses_the_shell_even_if_it_was_added_by_mistake():
    prompts, ran = _run("Get-ChildItem", cloud_mode=True)

    assert prompts == []
    assert ran == []


def test_the_model_is_told_why_a_call_was_refused():
    @tool
    def terminal_exec(command: str) -> str:
        """Stand-in for the real shell tool."""
        return "ok"

    agent = Agent(
        model=ScriptedModel([tool_call("terminal_exec", {"command": "rm -rf /"}), "ok"]),
        tools=[terminal_exec],
        interventions=[tool_policy(cloud_mode=False), approval_gate(RecordingAsk())],
        callback_handler=None,
    )
    agent("go")

    assert "policy" in _last_tool_result(agent.messages).lower()


def test_other_tools_are_not_affected():
    calls = []

    @tool
    def get_notes() -> str:
        """Read notes."""
        calls.append(1)
        return "notes"

    agent = Agent(
        model=ScriptedModel([tool_call("get_notes"), "ok"]),
        tools=[get_notes],
        interventions=[tool_policy(cloud_mode=True), approval_gate(RecordingAsk())],
        callback_handler=None,
    )
    agent("go")

    assert calls == [1]
