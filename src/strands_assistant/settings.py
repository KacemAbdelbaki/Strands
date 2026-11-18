import os
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parents[1]
_DEFAULT_DATA_DIR = (
    PROJECT_ROOT
    if (PROJECT_ROOT / "credentials").exists()
    else Path.home() / ".strands_assistant"
)
DATA_DIR = Path(os.getenv("STRANDS_DATA_DIR", str(_DEFAULT_DATA_DIR))).expanduser()
CREDENTIALS_DIR = DATA_DIR / "credentials"
MEMORY_DB_DIR = DATA_DIR / "memory_db"  # old Mem0/Chroma store, read once by migrate_memory
# Everything the agents keep between runs: memory and chat history. Contains personal data.
AGENT_STATE_DIR = DATA_DIR / "agent_state"
GEMINI_MODEL_ID = "gemini-3.1-flash-lite"


def is_cloud_mode() -> bool:
    """True on the server, where the agent must not have a shell next to its tokens and keys."""
    return os.getenv("CLOUD_MODE", "").strip().lower() == "true"
