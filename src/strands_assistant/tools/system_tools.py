import os
import signal
import subprocess

from strands import tool
import html
from strands_tools.utils.user_input import get_user_input

_MAX_OUTPUT_CHARS = 10_000


def _truncate(text: str, limit: int = _MAX_OUTPUT_CHARS) -> str:
    if len(text) <= limit:
        return text
    half = limit // 2
    return f"{text[:half]}\n...[truncated]...\n{text[-half:]}"


@tool
def terminal_exec(command: str) -> str:
    """Execute a shell command on the user's machine after the user approves it.

    Args:
        command: The shell command to run.

    Returns:
        The exit code, stdout and stderr of the command, or a message if the user declined.
    """
    if os.getenv("BYPASS_TOOL_CONSENT", "").lower() != "true":
        # get_user_input renders the prompt as prompt_toolkit HTML, so escape the command
        answer = get_user_input(f"Run command: {html.escape(command)} [y/N]", default="n")
        if answer.strip().lower() not in ("y", "yes"):
            return "The user declined to run this command."
    proc = subprocess.Popen(
        command,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        start_new_session=(os.name != "nt"),
    )
    try:
        timeout = int(os.getenv("TERMINAL_TIMEOUT", "60"))
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_process_tree(proc)
        proc.communicate()
        return f"Command timed out after {timeout} seconds."
    return (
        f"exit code: {proc.returncode}\n"
        f"stdout:\n{_truncate(stdout)}\n"
        f"stderr:\n{_truncate(stderr)}"
    )


def _kill_process_tree(proc: subprocess.Popen) -> None:
    """Kill the shell and its children (killing only the shell leaves them holding the output pipes)."""
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
    else:
        os.killpg(proc.pid, signal.SIGKILL)
