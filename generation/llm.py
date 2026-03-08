"""
LLM wrapper using LiteLLM.

Provides a single unified interface to:
  - Local Ollama models  (mistral, llama3.2, gemma3, qwen2.5, phi4, …)
  - OpenAI API          (openai/gpt-4o, openai/gpt-4o-mini, …)
  - Anthropic API       (anthropic/claude-sonnet-4-6, anthropic/claude-haiku-4-5-20251001, …)
  - Mistral API         (mistral/mistral-large-latest, …)
  - Any OpenAI-compatible endpoint

Swapping the model is a single config change — the rest of the system is
completely unaware of which provider is in use.
"""

import logging
from dataclasses import dataclass
from typing import Optional

import litellm
from litellm import completion

logger = logging.getLogger(__name__)

# Suppress LiteLLM's verbose success/failure logging in the UI
litellm.set_verbose = False

# ── Model recommendations ──────────────────────────────────────────────────

MODEL_RECOMMENDATIONS = {
    "8GB RAM":    ("ollama/mistral", "Mistral 7B Q4"),
    "16GB RAM":   ("ollama/llama3.2", "Llama 3.2 8B"),
    "24GB+ RAM":  ("ollama/qwen2.5:14b", "Qwen 2.5 14B"),
    "API (good)": ("openai/gpt-4o-mini", "GPT-4o-mini"),
    "API (best)": ("anthropic/claude-sonnet-4-6", "Claude Sonnet 4.6"),
}

# Models that run via Ollama locally
OLLAMA_MODELS = [
    "ollama/mistral",
    "ollama/llama3.2",
    "ollama/llama3.2:3b",
    "ollama/llama3.1",
    "ollama/llama3.1:8b",
    "ollama/gemma3",
    "ollama/gemma3:9b",
    "ollama/qwen2.5:14b",
    "ollama/qwen2.5:7b",
    "ollama/phi4",
]

# API-backed models (provider/ prefix = explicit routing, avoids LiteLLM guessing)
API_MODELS = [
    "openai/gpt-4o",
    "openai/gpt-4o-mini",
    "anthropic/claude-opus-4-6",
    "anthropic/claude-sonnet-4-6",
    "anthropic/claude-haiku-4-5-20251001",
    "mistral/mistral-large-latest",
    "mistral/mistral-small-latest",
]

ALL_MODELS = OLLAMA_MODELS + API_MODELS


# ── Config dataclass ──────────────────────────────────────────────────────


@dataclass
class LLMConfig:
    model: str = "ollama/mistral"
    temperature: float = 0.1       # Low temp for factual compliance answers
    max_tokens: int = 2048
    api_key: Optional[str] = None  # For API-backed models; reads from env if None
    api_base: Optional[str] = None # Override for custom Ollama base URL


# ── LLM wrapper ───────────────────────────────────────────────────────────


class LLMClient:
    """
    Thin LiteLLM wrapper. Exposes two methods:
    - complete(system, user)  → str  (standard chat completion)
    - stream(system, user)    → Iterator[str]  (streaming for UI)
    """

    def __init__(self, config: LLMConfig):
        self.config = config
        self._setup_api_keys()

    def _setup_api_keys(self) -> None:
        """
        Set API keys from environment variables for providers that don't
        support per-call key passing (legacy fallback only).
        LiteLLM picks up standard env vars (OPENAI_API_KEY, ANTHROPIC_API_KEY,
        etc.) automatically. Explicit api_key is now passed per-call via
        _build_kwargs() to avoid leaking across sessions in multi-user deploys.
        """
        pass  # Keys are now passed per-call in _build_kwargs()

    def complete(self, system: str, user: str) -> str:
        """
        Blocking chat completion.

        Returns the assistant message content as a string.
        Raises RuntimeError on API/model errors with a user-friendly message.
        """
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        kwargs = self._build_kwargs()

        try:
            response = completion(messages=messages, **kwargs)
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"LLM completion failed: {e}")
            raise RuntimeError(self._friendly_error(e)) from e

    def stream(self, system: str, user: str):
        """
        Streaming chat completion. Yields string chunks as they arrive.
        Used by the Streamlit UI to display tokens as they stream in.
        """
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        kwargs = self._build_kwargs()
        kwargs["stream"] = True

        try:
            response = completion(messages=messages, **kwargs)
            for chunk in response:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
        except Exception as e:
            logger.error(f"LLM streaming failed: {e}")
            raise RuntimeError(self._friendly_error(e)) from e

    def _build_kwargs(self) -> dict:
        kwargs: dict = {
            "model": self.config.model,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        if self.config.api_base:
            kwargs["api_base"] = self.config.api_base
        # Pass api_key per-call to avoid writing to global os.environ,
        # which would leak across sessions in multi-user deployments.
        if self.config.api_key:
            kwargs["api_key"] = self.config.api_key
        return kwargs

    @staticmethod
    def _friendly_error(e: Exception) -> str:
        msg = str(e).lower()
        if "connection" in msg or "refused" in msg:
            return (
                "Cannot connect to Ollama. "
                "Is it running? Try: `ollama serve` in a terminal."
            )
        if "api_key" in msg or "unauthorized" in msg or "401" in msg:
            return "Invalid or missing API key. Check your key in the sidebar."
        if "model" in msg and "not found" in msg:
            return (
                f"Model not found. For Ollama, run: "
                f"`ollama pull {LLMClient._extract_model_name(str(e))}`"
            )
        return f"LLM error: {e}"

    @staticmethod
    def _extract_model_name(error_str: str) -> str:
        """Best-effort extraction of model name from an error string."""
        import re
        match = re.search(r"'([^']+)'", error_str)
        return match.group(1) if match else "mistral"


def make_llm_callable(client: LLMClient):
    """
    Return a simple (system, user) -> str callable wrapping the LLMClient.
    Used by the HyPE enrichment module which expects this interface.
    """
    def call(system: str, user: str) -> str:
        return client.complete(system=system, user=user)
    return call
