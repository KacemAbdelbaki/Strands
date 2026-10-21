import html
import os
import signal
import subprocess

from strands import tool
from strands_tools.utils.user_input import get_user_input

_TIMEOUT_SECONDS = int(os.getenv("TERMINAL_TIMEOUT", "60"))
_MAX_OUTPUT_CHARS = 10_000


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
        start_new_session=(os.name != "nt"),
    )
    try:
        stdout, stderr = proc.communicate(timeout=_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        _kill_process_tree(proc)
        proc.communicate()
        return f"Command timed out after {_TIMEOUT_SECONDS} seconds."
    output = f"exit code: {proc.returncode}\nstdout:\n{stdout}\nstderr:\n{stderr}"
    return output[:_MAX_OUTPUT_CHARS]


def _kill_process_tree(proc: subprocess.Popen) -> None:
    """Kill the shell and its children (killing only the shell leaves them holding the output pipes)."""
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
    else:
        os.killpg(proc.pid, signal.SIGKILL)

