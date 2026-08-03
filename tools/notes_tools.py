from pathlib import Path
from strands import tool

@tool
def take_note(note: str):
    """Take a note and save it to a file."""
    note_path = Path("./notes/note.txt")
    note_path.parent.mkdir(parents=True, exist_ok=True)
    with open(note_path, "a") as note_file:
        note_file.write(note + "\n")
    return "Note " + note + " taken successfully."

@tool
def get_notes():
    """Get all available notes."""
    note_path = Path("./notes/note.txt")
    if note_path.exists():
        with open(note_path, "r") as note_file:
            lines = note_file.readlines()
            return lines
    else:
        return "you have no available notes."
