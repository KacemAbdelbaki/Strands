"""
Strands Personal Assistant — MCP Server

Wraps the Strands Agent in a FastMCP server.
Supports two transports via TRANSPORT env var:
  - stdio  (default): for local use with Claude Desktop / Claude Code
  - http   : streamable-http for containerized / remote use
"""

import logging
import os
import sys

from dotenv import load_dotenv

load_dotenv()

# Configure logging to stderr (stdout is reserved for stdio MCP transport)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FastMCP server
# ---------------------------------------------------------------------------

# from mcp.server.fastmcp import FastMCP
from fastmcp import FastMCP

mcp = FastMCP(
    "Strands Personal Assistant",
    instructions=(
        "A personal assistant with persistent memory, web search, "
        "and time awareness. Send any message to ask_assistant."
    ),
)

# Lazy-init the agent so the server starts fast and model loading
# only happens on the first request.
_agent = None


def _get_agent():
    global _agent
    if _agent is None:
        from agent import create_agent

        logger.info("Creating Strands Agent (first request)...")
        _agent = create_agent()
        logger.info("Agent ready.")
    return _agent


@mcp.tool()
def ask_assistant(message: str) -> str:
    """Send a message to the personal assistant.

    The assistant has persistent memory, web search, and time awareness.
    It will remember facts you share and recall them in future conversations.

    Args:
        message: Your message or question for the assistant.

    Returns:
        The assistant's response.
    """
    agent = _get_agent()
    logger.info("Received message: %s", message[:100])

    try:
        response = agent(message)
        result = str(response)
        logger.info("Response length: %d chars", len(result))
        return result
    except Exception as e:
        logger.error("Agent error: %s", e, exc_info=True)
        return f"Error: {e}"


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    transport = os.getenv("TRANSPORT", "stdio").lower()

    if transport == "stdio":
        logger.info("Starting MCP server with stdio transport")
        mcp.run(transport="stdio")

    elif transport == "http":
        host = os.getenv("HOST", "0.0.0.0")
        port = int(os.getenv("PORT", "8000"))
        logger.info("Starting MCP server with streamable-http on %s:%d", host, port)
        mcp.run(transport="streamable-http", host=host, port=port)

    else:
        logger.error("Unknown TRANSPORT='%s'. Use 'stdio' or 'http'.", transport)
        sys.exit(1)
