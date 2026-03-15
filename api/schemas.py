"""Pydantic request and response schemas for the FastAPI layer."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ModelOverride(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    provider: Literal["ollama", "openai", "anthropic", "mistral", "gemini", "openai_compatible"] | None = None
    model: str | None = None
    api_base: str | None = None
    api_key: str | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=64, le=8192)
    timeout_seconds: float | None = Field(default=None, gt=0.0, le=600.0)


UserRole = Literal[
    "provider",
    "deployer",
    "distributor",
    "importer",
    "authorized_representative",
    "affected_person",
    "user",
    "other",
]


class SystemContextRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    id: str | None = None
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    system_type: str = Field(min_length=1)
    catalog: str | None = None
    level_of_risk: str | None = None
    confidence: int | None = Field(default=None, ge=0, le=100)


class QueryRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    question: str = Field(min_length=3)
    sources: list[str] | None = None
    languages: list[str] | None = None
    top_k: int = Field(default=5, ge=1, le=10)
    user_role: UserRole | None = None
    system: SystemContextRequest | None = None
    model: ModelOverride | None = None


class CitationResponse(BaseModel):
    index: int
    id: str
    label: str
    source: str
    language: str
    chunk_type: str
    title: str | None = None
    article_number: str | None = None
    recital_number: str | None = None
    annex_number: str | None = None
    page_start: int
    page_end: int
    excerpt: str


class QueryResponse(BaseModel):
    question: str
    answer: str
    citations: list[CitationResponse]
    confidence: float
    low_confidence: bool
    warning: str | None = None
    answer_mode: str
    retrieval_debug: dict[str, object] = Field(default_factory=dict)


class IngestRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    pdf_path: str = Field(min_length=1)
    source: str = Field(min_length=1)
    language: str | None = None
    generate_hypothetical_questions: bool = False
    model: ModelOverride | None = None


class IngestResponse(BaseModel):
    status: str
    pdf_path: str
    source: str
    language: str
    chunk_count: int
    hypothetical_question_count: int


class SourceSummaryResponse(BaseModel):
    id: str
    source: str
    chunk_count: int
    languages: list[str]
    articles: int
    recitals: int
    annexes: int


class DeleteSourceResponse(BaseModel):
    status: str
    deleted_source: str


class HealthResponse(BaseModel):
    status: str
    version: str
    dependencies: dict[str, bool]
    store: dict[str, object]


class ProviderOptionResponse(BaseModel):
    id: str
    label: str
    requires_api_key: bool
    default_model: str
    default_base_url: str | None = None


class HardwareRecommendationResponse(BaseModel):
    hardware: str
    recommendation: str


class ConfigResponse(BaseModel):
    app_name: str
    app_version: str
    default_top_k: int
    default_model: str
    default_provider: str
    default_api_base: str | None = None
    provider_options: list[ProviderOptionResponse]
    hardware_recommendations: list[HardwareRecommendationResponse]


class OllamaModelResponse(BaseModel):
    name: str
    size: int = 0
    modified_at: str | None = None


class OllamaModelsResponse(BaseModel):
    status: str
    base_url: str
    models: list[OllamaModelResponse]


class OllamaPullRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    model: str = Field(min_length=1)
    base_url: str | None = None


class OllamaPullResponse(BaseModel):
    status: str
    base_url: str
    model: str


class AISystemResponse(BaseModel):
    id: str
    name: str
    description: str
    system_type: str
    catalog: str = "Default"
    level_of_risk: str | None = None
    confidence: int | None = Field(default=None, ge=0, le=100)
    analysis_summary: str | None = None
    analysis_status: Literal["new", "analyzed", "error"] = "new"
    analysis_error: str | None = None
    analysis_citations: list[str] = Field(default_factory=list)
    last_user_role: UserRole | None = None
    last_provider: str | None = None
    last_model: str | None = None
    last_analyzed_at: str | None = None
    created_at: str
    updated_at: str


class AISystemUpsertRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    system_type: str = Field(min_length=1)
    catalog: str | None = None


class AISystemUpdateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    system_type: str = Field(min_length=1)
    catalog: str | None = None


class AISystemUpsertResponse(BaseModel):
    status: str
    created: bool
    system: AISystemResponse


class AISystemDeleteResponse(BaseModel):
    status: str
    deleted_system_id: str


class AISystemAnalysisRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    system_ids: list[str] = Field(min_length=1)
    force: bool = False
    user_role: UserRole | None = None
    model: ModelOverride | None = None


class AISystemAnalysisFailure(BaseModel):
    system_id: str
    message: str


class AISystemAnalysisResponse(BaseModel):
    status: str
    analyzed: list[AISystemResponse]
    skipped: list[AISystemResponse]
    failures: list[AISystemAnalysisFailure] = Field(default_factory=list)


class AISystemImportRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    systems: list[AISystemResponse] = Field(min_length=1)
    mode: Literal["merge", "replace"] = "merge"


class AISystemImportResponse(BaseModel):
    status: str
    mode: Literal["merge", "replace"]
    total: int
    imported: int
    updated: int
