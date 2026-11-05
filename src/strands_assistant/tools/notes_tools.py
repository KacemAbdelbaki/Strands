from pathlib import Path
from strands import tool
from strands_assistant.settings import NOTES_DIR

@tool
def take_note(note: str):
    """Take a note and save it to a file."""
    note_path = NOTES_DIR / "note.txt"
    note_path.parent.mkdir(parents=True, exist_ok=True)
    with open(note_path, "a", encoding="utf-8") as note_file:
        note_file.write(note + "\n")
    return "Note " + note + " taken successfully."

@tool
def get_notes():
    """Get all available notes."""
    note_path = NOTES_DIR / "note.txt"
    if note_path.exists():
        with open(note_path, "r", encoding="utf-8") as note_file:
            lines = note_file.readlines()
            return lines
    else:
        return "you have no available notes."
