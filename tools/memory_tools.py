import logging
from strands import tool
from logic.memory import _get_memory

logger = logging.getLogger(__name__)
_DEFAULT_USER_ID = "default_user"

@tool
def remember(content: str, user_id: str = _DEFAULT_USER_ID) -> str:
    """Store a fact or preference in persistent memory.
    Args:
        content: The fact or information to remember.
        user_id: Identifier for the user (default: "default_user").
    Returns:
        Confirmation message.
    """
    mem = _get_memory()
    result = mem.add(content, user_id=user_id)
    logger.info("Memory stored: %s", result)
    return f"Remembered: {content}"


@tool
def recall(query: str, user_id: str = _DEFAULT_USER_ID) -> str:
    """Search persistent memory for facts relevant to a query.
    Args:
        query: What to search for in memory.
        user_id: Identifier for the user (default: "default_user").
    Returns:
        Relevant memories as a formatted string, or a message if none found.
    """
    mem = _get_memory()
    results = mem.search(query, filters={"user_id": user_id})
    if not results or (isinstance(results, dict) and not results.get("results")):
        return "No relevant memories found."

    # Handle both dict and list return formats
    memories = results.get("results", results) if isinstance(results, dict) else results
    if not memories:
        return "No relevant memories found."

    lines = []
    for i, entry in enumerate(memories, 1):
        text = entry.get("memory", entry.get("text", str(entry)))
        lines.append(f"{i}. {text}")
    return "Relevant memories:\n" + "\n".join(lines)


@tool
def list_memories(user_id: str = _DEFAULT_USER_ID) -> str:
    """List all stored memories for a user.
    Args:
        user_id: Identifier for the user (default: "default_user").
    Returns:
        All memories as a formatted string, or a message if none exist.
    """
    mem = _get_memory()
    results = mem.get_all(filters={"user_id": user_id})

    memories = results.get("results", results) if isinstance(results, dict) else results
    if not memories:
        return "No memories stored yet."

    lines = []
    for i, entry in enumerate(memories, 1):
        text = entry.get("memory", entry.get("text", str(entry)))
        lines.append(f"{i}. {text}")
    return f"All memories ({len(memories)}):\n" + "\n".join(lines)
