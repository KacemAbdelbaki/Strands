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
NOTES_DIR = DATA_DIR / "notes"
MEMORY_DB_DIR = DATA_DIR / "memory_db"
GEMINI_MODEL_ID = "gemini-3.1-flash-lite"
