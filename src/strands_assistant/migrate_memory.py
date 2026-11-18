"""One-time copy of the old Mem0 memories into the new Markdown memory store.

Reads Chroma's SQLite file directly, so it needs neither `mem0ai` nor `chromadb`. Safe to run more
than once: facts already in the store are skipped. The old `memory_db/` folder is left untouched;
delete it yourself once the result looks right.

    python -m strands_assistant.migrate_memory
"""

import asyncio
import sqlite3
import sys
from pathlib import Path

from strands_assistant import settings
from strands_assistant.memory import UserMemoryStore, create_memory_store

MEM0_COLLECTION = "assistant_memory"
MIGRATED_HEADING = "# Migrated from Mem0"


def read_mem0_memories(db_path: Path) -> list[str]:
    """The memory text Mem0 stored, in insertion order. Mem0 keeps it under the `data` metadata key."""
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        rows = db.execute(
            """
            SELECT m.string_value
            FROM embedding_metadata m
            JOIN embeddings e ON e.id = m.id
            JOIN segments s ON s.id = e.segment_id
            JOIN collections c ON c.id = s.collection
            WHERE c.name = ? AND m.key = 'data' AND m.string_value IS NOT NULL
            ORDER BY e.id
            """,
            (MEM0_COLLECTION,),
        ).fetchall()
    finally:
        db.close()
    return [value.strip() for (value,) in rows if value.strip()]


async def migrate(db_path: Path, store: UserMemoryStore) -> int:
    """Copy Mem0 memories into `store` under one heading. Returns how many facts were added."""
    existing = "\n".join(await store.list_all())
    new_facts = [fact for fact in read_mem0_memories(db_path) if f"- {fact}" not in existing]
    if new_facts:
        await store.add(MIGRATED_HEADING + "\n" + "\n".join(f"- {fact}" for fact in new_facts))
    return len(new_facts)


def main() -> None:
    db_path = settings.MEMORY_DB_DIR / "chroma.sqlite3"
    if not db_path.exists():
        sys.exit(f"No Mem0 database found at {db_path}")
    # Extraction is off: this store is only written to here, never attached to an agent
    store = create_memory_store(settings.AGENT_STATE_DIR, extraction=False)
    count = asyncio.run(migrate(db_path, store))
    print(f"Migrated {count} memories into {settings.AGENT_STATE_DIR / 'memory' / store.name}")


if __name__ == "__main__":
    main()
