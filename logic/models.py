import os
import logging

logger = logging.getLogger(__name__)

def _build_model():
    """Return the appropriate Strands model based on MODEL_PROVIDER env var."""
    provider = os.getenv("MODEL_PROVIDER", "groq").lower()

    if provider == "groq":
        from strands.models.litellm import LiteLLMModel

        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError(
                "MODEL_PROVIDER=groq but GROQ_API_KEY is not set. "
                "Get a free key at https://console.groq.com"
            )
        return LiteLLMModel(
            model_id="groq/llama-3.3-70b-versatile",
            client_args={"api_key": api_key},
        )

    elif provider == "gemini":
        from strands.models.gemini import GeminiModel

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "MODEL_PROVIDER=gemini but GEMINI_API_KEY is not set. "
                "Get a free key at https://aistudio.google.com"
            )
        return GeminiModel(
            model_id="gemini-3.1-flash-lite",
            client_args={"api_key": api_key},
        )

    elif provider == "ollama":
        from strands.models.ollama import OllamaModel

        host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        return OllamaModel(
            model_id="qwen3:8b",
            host=host,
        )

    else:
        raise ValueError(
            f"Unknown MODEL_PROVIDER='{provider}'. "
            "Choose from: groq, gemini, ollama"
        )
