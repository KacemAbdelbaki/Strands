import os
import logging
from urllib.error import URLError
from urllib.request import urlopen

logger = logging.getLogger(__name__)



# ---------------------------------------------------------------------------
# Individual model builders
# ---------------------------------------------------------------------------

def _build_groq():
    """Build a Groq model via LiteLLM."""
    import litellm
    from strands.models.litellm import LiteLLMModel

    # Hide LiteLLM's "Give Feedback / Get Help" banner printed on every (retried) error
    litellm.suppress_debug_info = True

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not set. "
            "Get a free key at https://console.groq.com"
        )
    return LiteLLMModel(
        model_id="groq/openai/gpt-oss-20b",
        client_args={"api_key": api_key},
    )


def _build_gemini():
    """Build a Gemini model."""
    from strands.models.gemini import GeminiModel

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. "
            "Get a free key at https://aistudio.google.com"
        )
    return GeminiModel(
        model_id="gemini-3.1-flash-lite",
        client_args={"api_key": api_key},
    )


def _build_ollama():
    """Build an Ollama (local) model."""
    from strands.models.ollama import OllamaModel

    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    return OllamaModel(
        model_id="qwen3:8b",
        host=host,
    )



_BUILDERS = {
    "groq": _build_groq,
    "gemini": _build_gemini,
    "ollama": _build_ollama,
}


# ---------------------------------------------------------------------------
# Router factory
# ---------------------------------------------------------------------------

def _ollama_available() -> bool:
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
    try:
        with urlopen(f"{host}/api/tags", timeout=1):
            return True
    except (OSError, URLError):
        return False


def build_model(priority_env: str = "MODEL_PRIORITY", default: str = "gemini,groq,ollama"):
    """Build a ModelRouter with FallbackStrategy from a comma-separated priority list.

    Reads the priority from the `priority_env` env var (e.g. "gemini,groq,ollama"),
    falling back to `default`. Each agent passes its own env var so they can use
    different failover chains.

    Models whose keys are missing are skipped with a warning instead of
    crashing the entire startup.
    """
    from strands.models.routing import ModelRouter
    from strands.models.routing.fallback_strategy import FallbackStrategy

    priority_str = os.getenv(priority_env, default)
    priority = [p.strip().lower() for p in priority_str.split(",") if p.strip()]

    models = []
    loaded = []
    for name in priority:
        builder = _BUILDERS.get(name)
        if builder is None:
            logger.warning("Unknown model provider '%s' in %s — skipping.", name, priority_env)
            continue
        if name == "ollama" and not _ollama_available():
            logger.info("Skipping Ollama because %s is unavailable.", os.getenv("OLLAMA_HOST", "http://localhost:11434"))
            continue
        try:
            models.append(builder())
            loaded.append(name)
            logger.info("Loaded model provider: %s", name)
        except RuntimeError as exc:
            # Missing API key — skip this provider instead of crashing
            logger.warning("Skipping provider '%s': %s", name, exc)


    if not models:
        raise RuntimeError(
            f"No usable model providers for {priority_env}. Set GEMINI_API_KEY and/or "
            "GROQ_API_KEY, or start Ollama and set OLLAMA_HOST."
        )

    router = ModelRouter(
        models=models,
        strategy=FallbackStrategy(),
    )
    logger.info(
        "ModelRouter ready — failover chain: %s", " → ".join(loaded),
    )
    return router
