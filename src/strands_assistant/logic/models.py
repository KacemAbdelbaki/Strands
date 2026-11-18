import base64
import os
import logging
from copy import deepcopy
from urllib.error import URLError
from urllib.request import urlopen

from strands.models.gemini import GeminiModel

logger = logging.getLogger(__name__)

# Google's documented placeholder for function calls Gemini didn't make itself (the same value LiteLLM uses):
# https://ai.google.dev/gemini-api/docs/thought-signatures#faqs
PLACEHOLDER_THOUGHT_SIGNATURE = base64.b64encode(b"skip_thought_signature_validator").decode("ascii")


class SignatureSafeGeminiModel(GeminiModel):
    """Gemini that accepts tool calls made earlier in the run by another provider.

    The router switches provider mid-run, after a failed model call (e.g. Groq hits its rate limit right after
    calling get_emails). Gemini 3 rejects history whose function calls have no thought_signature
    (`400 missing thought_signature`), so each unsigned call gets the placeholder. Only the copy sent to Gemini
    changes: the agent's history stays clean for the next provider.
    """

    @staticmethod
    def with_placeholder_signatures(messages):
        patched = deepcopy(messages)
        for message in patched:
            for block in message.get("content", []):
                tool_use = block.get("toolUse")
                if tool_use is not None and not tool_use.get("reasoningSignature"):
                    tool_use["reasoningSignature"] = PLACEHOLDER_THOUGHT_SIGNATURE
        return patched

    async def stream(self, messages, *args, **kwargs):
        async for event in super().stream(self.with_placeholder_signatures(messages), *args, **kwargs):
            yield event



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
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. "
            "Get a free key at https://aistudio.google.com"
        )
    return SignatureSafeGeminiModel(
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


def _load_providers(priority_env: str, default: str, *, limit: int | None = None) -> list[tuple[str, object]]:
    """Build the providers named in `priority_env` (or `default`), in order, skipping unusable ones."""
    priority_str = os.getenv(priority_env, default)
    priority = [p.strip().lower() for p in priority_str.split(",") if p.strip()]

    loaded = []
    for name in priority:
        if limit is not None and len(loaded) >= limit:
            break
        builder = _BUILDERS.get(name)
        if builder is None:
            logger.warning("Unknown model provider '%s' in %s — skipping.", name, priority_env)
            continue
        if name == "ollama" and not _ollama_available():
            logger.info("Skipping Ollama because %s is unavailable.", os.getenv("OLLAMA_HOST", "http://localhost:11434"))
            continue
        try:
            loaded.append((name, builder()))
            logger.info("Loaded model provider: %s", name)
        except RuntimeError as exc:
            # Missing API key — skip this provider instead of crashing
            logger.warning("Skipping provider '%s': %s", name, exc)
    return loaded


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

    loaded = _load_providers(priority_env, default)
    if not loaded:
        raise RuntimeError(
            f"No usable model providers for {priority_env}. Set GEMINI_API_KEY and/or "
            "GROQ_API_KEY, or start Ollama and set OLLAMA_HOST."
        )

    router = ModelRouter(
        models=[model for _, model in loaded],
        strategy=FallbackStrategy(),
    )
    logger.info(
        "ModelRouter ready — failover chain: %s", " → ".join(name for name, _ in loaded),
    )
    return router


def build_single_model(priority_env: str, default: str):
    """The first usable provider from a priority list, as one model with no fallback, or None.

    For the SDK's `aux_model`, which rejects a router. None means side calls use the main model.
    """
    loaded = _load_providers(priority_env, default, limit=1)
    if not loaded:
        logger.info("No usable provider for %s; side calls will use the main model.", priority_env)
        return None
    name, model = loaded[0]
    logger.info("%s: using %s", priority_env, name)
    return model
