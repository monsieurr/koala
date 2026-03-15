"""Runtime settings and shared service factories for the API layer."""

from __future__ import annotations

from functools import lru_cache
import os
from pathlib import Path
import shutil
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from generation.chain import ComplianceAnswerChain
from generation.llm import LLMSettings
from generation.system_analysis import AISystemAnalyzer
from ingestion.store import ChromaVectorStore
from api.system_store import AISystemJsonStore
from retrieval.retriever import HybridRetriever


class ProviderOption(BaseModel):
    id: str
    label: str
    requires_api_key: bool
    default_model: str
    default_base_url: str | None = None


class HardwareRecommendation(BaseModel):
    hardware: str
    recommendation: str


class AppSettings(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    app_name: str = "AI Act Compliance Tool API"
    app_version: str = "0.1.0"
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list[str] = Field(default_factory=list)
    cors_origin_regex: str | None = None
    chroma_persist_directory: str = "data/chroma"
    ai_systems_path: str = "data/ai_systems.json"
    chroma_collection_name: str = "legal_documents"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    default_top_k: int = 5
    default_llm: LLMSettings = Field(default_factory=LLMSettings.from_env)
    provider_options: list[ProviderOption] = Field(default_factory=list)
    hardware_recommendations: list[HardwareRecommendation] = Field(default_factory=list)

    @classmethod
    def from_env(cls) -> "AppSettings":
        default_llm = LLMSettings.from_env()
        cors_origins = _parse_csv(
            os.getenv(
                "CORS_ORIGINS",
                "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173",
            )
        )
        chroma_persist_directory = os.getenv("CHROMA_PERSIST_DIRECTORY", "data/chroma")
        if os.getenv("VERCEL") == "1" and chroma_persist_directory.startswith("data/"):
            chroma_persist_directory = "/tmp/chroma"
        cors_origin_regex = os.getenv("CORS_ORIGIN_REGEX", "").strip()
        if not cors_origin_regex:
            cors_origin_regex = (
                r"^http://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+|"
                r"172\.(1[6-9]|2\d|3[0-1])\.\d+\.\d+)(:\d+)?$"
            )
        return cls(
            host=os.getenv("API_HOST", "0.0.0.0"),
            port=int(os.getenv("API_PORT", "8000")),
            cors_origins=cors_origins,
            cors_origin_regex=cors_origin_regex,
            chroma_persist_directory=chroma_persist_directory,
            ai_systems_path=os.getenv("AI_SYSTEMS_PATH", "data/ai_systems.json"),
            chroma_collection_name=os.getenv("CHROMA_COLLECTION_NAME", "legal_documents"),
            embedding_model=os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
            reranker_model=os.getenv("RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2"),
            default_top_k=int(os.getenv("DEFAULT_TOP_K", "5")),
            default_llm=default_llm,
            provider_options=[
                ProviderOption(
                    id="ollama",
                    label="Local (Ollama)",
                    requires_api_key=False,
                    default_model="llama3.1:8b",
                    default_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
                ),
                ProviderOption(
                    id="openai",
                    label="OpenAI (GPT)",
                    requires_api_key=True,
                    default_model="gpt-4.1-mini",
                ),
                ProviderOption(
                    id="anthropic",
                    label="Anthropic (Claude)",
                    requires_api_key=True,
                    default_model="claude-sonnet-4-0",
                ),
                ProviderOption(
                    id="gemini",
                    label="Google (Gemini)",
                    requires_api_key=True,
                    default_model="gemini-2.5-pro",
                ),
                ProviderOption(
                    id="mistral",
                    label="Mistral API",
                    requires_api_key=True,
                    default_model="mistral-small-latest",
                ),
                ProviderOption(
                    id="openai_compatible",
                    label="Custom API (OpenAI-compatible)",
                    requires_api_key=True,
                    default_model="custom-model",
                    default_base_url=os.getenv("LLM_API_BASE", ""),
                ),
            ],
            hardware_recommendations=[
                HardwareRecommendation(hardware="8GB RAM", recommendation="Mistral 7B Q4"),
                HardwareRecommendation(hardware="16GB RAM", recommendation="Llama 3.1 8B or Gemma 2 9B"),
                HardwareRecommendation(hardware="24GB+ RAM", recommendation="Qwen 2.5 14B"),
                HardwareRecommendation(hardware="API", recommendation="GPT-4o-mini, GPT-4o, or Claude Sonnet"),
            ],
        )


def _parse_csv(raw_value: str) -> list[str]:
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def _seed_chroma_if_needed(persist_directory: str, seed_directory: str | None) -> None:
    if not seed_directory:
        return
    seed_path = Path(seed_directory)
    if not seed_path.exists():
        return
    persist_path = Path(persist_directory)
    if persist_path.exists() and any(persist_path.iterdir()):
        return
    try:
        persist_path.mkdir(parents=True, exist_ok=True)
        for item in seed_path.iterdir():
            destination = persist_path / item.name
            if item.is_dir():
                shutil.copytree(item, destination, dirs_exist_ok=True)
            else:
                shutil.copy2(item, destination)
    except Exception:
        return


@lru_cache
def get_settings() -> AppSettings:
    return AppSettings.from_env()


@lru_cache
def get_store() -> ChromaVectorStore:
    settings = get_settings()
    seed_dir = os.getenv("KOALA_CHROMA_SEED_DIR")
    if os.getenv("VERCEL") == "1" and not seed_dir:
        seed_dir = "data/chroma"
    _seed_chroma_if_needed(settings.chroma_persist_directory, seed_dir)
    return ChromaVectorStore(
        persist_directory=settings.chroma_persist_directory,
        collection_name=settings.chroma_collection_name,
        embedding_model=settings.embedding_model,
    )


@lru_cache
def get_system_store() -> AISystemJsonStore:
    settings = get_settings()
    return AISystemJsonStore(settings.ai_systems_path)


@lru_cache
def get_answer_chain() -> ComplianceAnswerChain:
    settings = get_settings()
    store = get_store()
    retriever = HybridRetriever(
        store,
        reranker_model=settings.reranker_model,
    )
    return ComplianceAnswerChain(
        retriever,
        default_llm_settings=settings.default_llm,
    )


@lru_cache
def get_system_analyzer() -> AISystemAnalyzer:
    settings = get_settings()
    return AISystemAnalyzer(
        get_answer_chain().retriever,
        default_llm_settings=settings.default_llm,
    )


def build_runtime_llm_settings(
    default_settings: LLMSettings,
    overrides: dict[str, Any] | None,
) -> LLMSettings:
    if not overrides:
        return default_settings
    return default_settings.with_overrides(
        provider=overrides.get("provider"),
        model=overrides.get("model"),
        api_base=overrides.get("api_base"),
        api_key=overrides.get("api_key"),
        temperature=overrides.get("temperature"),
        max_tokens=overrides.get("max_tokens"),
        timeout_seconds=overrides.get("timeout_seconds"),
    )
