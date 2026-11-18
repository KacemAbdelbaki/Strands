"""Long-term memory through the SDK's MemoryManager and a Markdown file store.

Memories are plain Markdown files under `<AGENT_STATE_DIR>/memory/user/`, one per topic, so they can
be read and edited outside the app. The manager gives the agent `search_memory` and `add_memory`,
injects relevant memories before each model call, and extracts new facts in the background every few
turns. There is a single user, so no tool takes a user id: the model can't be talked into reading
someone else's memories.

Search is keyword overlap, so "where do I work?" can miss "my employer is X". A store backed by
embeddings fits the same `MemoryStore` protocol (`search` plus `add`) if the evals show it's needed.
"""

from pathlib import Path

from strands import tool
from strands.memory import MemoryManager
from strands.storage import LocalFileStorage
from strands.types.tools import AgentTool
from strands.vended_memory_stores.file_memory_store import FileMemoryStore

USER_STORE_NAME = "user"


class UserMemoryStore(FileMemoryStore):
    """The file store, plus a `list_memories` tool for "what do you know about me?" questions."""

    async def list_all(self) -> list[str]:
        entries = []
        for key in sorted(await self._storage.list("")):
            data = await self._storage.read(key)
            if data:
                entries.append(data.decode("utf-8", errors="replace").strip())
        return entries

    def get_tools(self) -> list[AgentTool]:
        store = self

        @tool
        async def list_memories() -> str:
            """List everything stored in long-term memory about the user.

            Use this when the user asks what you know or remember about them. To answer a specific
            question, prefer `search_memory`.
            """
            entries = await store.list_all()
            if not entries:
                return "No memories stored yet."
            return "\n\n".join(entries)

        return [list_memories]


def create_memory_store(state_dir: Path, *, extraction: bool = True) -> UserMemoryStore:
    """The user's memory store, kept under `state_dir`."""
    return UserMemoryStore(
        name=USER_STORE_NAME,
        description="Durable facts about the user: preferences, people, projects, work and plans.",
        storage=LocalFileStorage(str(state_dir)),
        extraction=extraction,
    )


def create_memory_manager(state_dir: Path) -> MemoryManager:
    """The Assistant's memory: search and add tools, automatic injection and background extraction."""
    # add_tool_config defaults to False, which would leave the agent unable to save on request
    return MemoryManager(stores=[create_memory_store(state_dir)], add_tool_config=True)
