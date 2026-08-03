import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_MEMORY_DB_PATH = str(Path(__file__).parent / "memory_db")

def _get_mem0_config():
    """Build the Mem0 config based on MEMORY_PROVIDER env var."""
    memory_provider = os.getenv("MEMORY_PROVIDER", "cloud").lower()
    
    base_config = {
        "vector_store": {
            "provider": "chroma",
            "config": {
                "collection_name": "assistant_memory",
                "path": _MEMORY_DB_PATH,
            },
        }
    }
    
    if memory_provider == "ollama":
        # Fully local memory
        base_config["llm"] = {
            "provider": "ollama",
            "config": {
                "model": "llama3.2:3b",
                "base_url": os.getenv("OLLAMA_HOST", "http://localhost:11434"),
            },
        }
        base_config["embedder"] = {
            "provider": "ollama",
            "config": {
                "model": "nomic-embed-text",
                "base_url": os.getenv("OLLAMA_HOST", "http://localhost:11434"),
            },
        }
    else:
        # Free cloud memory
        base_config["llm"] = {
            "provider": "gemini",
            "config": {
                "model": "gemini-3.5-flash-lite",
                "api_key": os.getenv("GEMINI_API_KEY"),
            },
        }
        base_config["embedder"] = {
            "provider": "gemini",
            "config": {
                "model": "gemini-embedding-001",
                "api_key": os.getenv("GEMINI_API_KEY"),
            },
        }
        
    return base_config

_memory = None

def _get_memory():
    """Lazy-init Mem0 Memory instance."""
    global _memory
    if _memory is None:
        mem0_api_key = os.getenv("MEM0_API_KEY")
        if mem0_api_key:
            from mem0 import MemoryClient
            logger.info("Initializing Mem0 managed platform")
            _memory = MemoryClient(api_key=mem0_api_key)
        else:
            from mem0 import Memory
            logger.info("Initializing local Mem0 with ChromaDB at %s", _MEMORY_DB_PATH)
            _memory = Memory.from_config(_get_mem0_config())
    return _memory
