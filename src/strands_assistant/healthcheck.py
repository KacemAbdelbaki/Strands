"""Container health check: fails if the data folder is missing or read-only.

Without this, a bad volume mount looks healthy until the agent loses a note or a memory.
"""

import sys
import tempfile
from pathlib import Path

from strands_assistant.settings import DATA_DIR


def data_dir_is_writable(data_dir: Path) -> bool:
    try:
        with tempfile.TemporaryFile(dir=data_dir):
            return True
    except OSError:
        return False


def main() -> None:
    if not data_dir_is_writable(DATA_DIR):
        sys.exit(f"Data folder is not writable: {DATA_DIR}")


if __name__ == "__main__":
    main()
