"""LiteLLM wrapper and runtime model settings."""

from __future__ import annotations

import os
from typing import Any, Literal, Sequence

from pydantic import BaseModel, ConfigDict, Field

Provider = Literal["ollama", "openai", "anthropic", "mistral", "gemini", "openai_compatible"]


class LLMDependencyError(RuntimeError):
    """Raised when the configured LLM backend cannot be used."""


class LLMSettings(BaseModel):
    """Runtime settings for the answer-generation model."""

    model_config = ConfigDict(str_strip_whitespace=True)

    provider: Provider = "ollama"
    model: str = "llama3.1:8b"
    api_base: str | None = "http://localhost:11434"
    api_key: str | None = None
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    max_tokens: int = Field(default=900, ge=64, le=8192)
    timeout_seconds: float = Field(default=60.0, gt=0.0, le=600.0)

    @classmethod
    def from_env(cls) -> "LLMSettings":
        provider = os.getenv("LLM_PROVIDER", "ollama")
        return cls(
            provider=provider,  # type: ignore[arg-type]
            model=os.getenv("LLM_MODEL", "llama3.1:8b"),
            api_base=cls.default_api_base_for(provider),  # type: ignore[arg-type]
            api_key=os.getenv("LLM_API_KEY")
            or os.getenv("OPENAI_API_KEY")
            or os.getenv("ANTHROPIC_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
            or os.getenv("MISTRAL_API_KEY"),
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.1")),
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "900")),
            timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "60")),
        )

    @property
    def litellm_model(self) -> str:
        if "/" in self.model:
            return self.model
        if self.provider == "ollama":
            return f"ollama/{self.model}"
        if self.provider == "anthropic":
            return f"anthropic/{self.model}"
        if self.provider == "mistral":
            return f"mistral/{self.model}"
        if self.provider == "gemini":
            return f"gemini/{self.model}"
        if self.provider == "openai_compatible":
            return f"openai/{self.model}"
        return self.model

    @staticmethod
    def default_api_base_for(provider: Provider) -> str | None:
        if provider == "ollama":
            return os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        if provider == "openai_compatible":
            return os.getenv("LLM_API_BASE")
        return None

    def with_overrides(
        self,
        *,
        provider: Provider | None = None,
        model: str | None = None,
        api_base: str | None = None,
        api_key: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        timeout_seconds: float | None = None,
    ) -> "LLMSettings":
        payload = self.model_dump()
        if provider is not None:
            payload["provider"] = provider
            if api_base is None:
                payload["api_base"] = self.default_api_base_for(provider)
        if model is not None:
            payload["model"] = model
        if api_base is not None:
            payload["api_base"] = api_base
        if api_key is not None:
            payload["api_key"] = api_key
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if timeout_seconds is not None:
            payload["timeout_seconds"] = timeout_seconds
        return LLMSettings.model_validate(payload)


class LiteLLMClient:
    """Minimal wrapper over LiteLLM chat completion."""

    def __init__(self, settings: LLMSettings) -> None:
        self.settings = settings

    def complete(self, messages: Sequence[dict[str, str]]) -> str:
        try:
            from litellm import completion
        except ImportError as exc:
            raise LLMDependencyError(
                "litellm is not installed. Install dependencies from requirements.txt."
            ) from exc

        kwargs: dict[str, Any] = {
            "model": self.settings.litellm_model,
            "messages": list(messages),
            "temperature": self.settings.temperature,
            "max_tokens": self.settings.max_tokens,
            "timeout": self.settings.timeout_seconds,
        }
        if self.settings.api_base:
            kwargs["api_base"] = self.settings.api_base
        if self.settings.api_key:
            kwargs["api_key"] = self.settings.api_key

        try:
            response = completion(**kwargs)
        except Exception as exc:
            raise LLMDependencyError(f"LLM request failed: {exc}") from exc

        content = response.choices[0].message.content
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts = [item.get("text", "") for item in content if isinstance(item, dict)]
            return "\n".join(part for part in parts if part).strip()
        raise LLMDependencyError("LLM response did not include text content.")

    def generate(self, prompt: str) -> str:
        return self.complete(
            [
                {
                    "role": "system",
                    "content": (
                        "You write concise legal retrieval queries based only on the provided legal text."
                    ),
                },
                {"role": "user", "content": prompt},
            ]
        )
