"""FastAPI route definitions."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from api.config import (
    AppSettings,
    build_runtime_llm_settings,
    get_answer_chain,
    get_settings,
    get_store,
    get_system_analyzer,
    get_system_store,
)
from api.system_store import StoredAISystem
from api.ollama import OllamaClientError, list_ollama_models, normalize_ollama_base_url, pull_ollama_model
from api.schemas import (
    AISystemAnalysisResponse,
    AISystemAnalysisRequest,
    AISystemDeleteResponse,
    AISystemImportRequest,
    AISystemImportResponse,
    AISystemResponse,
    AISystemUpdateRequest,
    AISystemUpsertRequest,
    AISystemUpsertResponse,
    ConfigResponse,
    DeleteSourceResponse,
    HealthResponse,
    IngestRequest,
    IngestResponse,
    OllamaModelsResponse,
    OllamaPullRequest,
    OllamaPullResponse,
    QueryRequest,
    QueryResponse,
    SourceSummaryResponse,
)
from generation.llm import LLMDependencyError, LiteLLMClient
from ingestion.parser import LegalDocumentParser, ParserDependencyError
from ingestion.store import StoreDependencyError
from retrieval.hype import HyPEGenerator

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health(
    settings: AppSettings = Depends(get_settings),
):
    dependencies = {
        "chromadb": importlib.util.find_spec("chromadb") is not None,
        "fitz": importlib.util.find_spec("fitz") is not None,
        "sentence_transformers": importlib.util.find_spec("sentence_transformers") is not None,
        "litellm": importlib.util.find_spec("litellm") is not None,
        "fastapi": importlib.util.find_spec("fastapi") is not None,
    }
    try:
        store_stats = get_store().stats()
        status = "ok"
    except Exception as exc:
        store_stats = {"error": str(exc)}
        status = "degraded"
    return HealthResponse(
        status=status,
        version=settings.app_version,
        dependencies=dependencies,
        store=store_stats,
    )


@router.get("/config", response_model=ConfigResponse)
def config(
    settings: AppSettings = Depends(get_settings),
):
    return ConfigResponse(
        app_name=settings.app_name,
        app_version=settings.app_version,
        default_top_k=settings.default_top_k,
        default_model=settings.default_llm.model,
        default_provider=settings.default_llm.provider,
        default_api_base=settings.default_llm.api_base,
        provider_options=[item.model_dump() for item in settings.provider_options],
        hardware_recommendations=[item.model_dump() for item in settings.hardware_recommendations],
    )


@router.get("/sources", response_model=list[SourceSummaryResponse])
def list_sources():
    try:
        return get_store().source_summaries()
    except StoreDependencyError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/models/ollama", response_model=OllamaModelsResponse)
def ollama_models(
    base_url: str | None = None,
    settings: AppSettings = Depends(get_settings),
):
    resolved_base_url = normalize_ollama_base_url(base_url, settings.default_llm.api_base or "http://localhost:11434")
    try:
        models = list_ollama_models(resolved_base_url)
        return OllamaModelsResponse(
            status="ok",
            base_url=resolved_base_url,
            models=models,
        )
    except OllamaClientError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/models/ollama/pull", response_model=OllamaPullResponse)
def pull_model(
    request: OllamaPullRequest,
    settings: AppSettings = Depends(get_settings),
):
    resolved_base_url = normalize_ollama_base_url(
        request.base_url,
        settings.default_llm.api_base or "http://localhost:11434",
    )
    try:
        result = pull_ollama_model(resolved_base_url, request.model)
        return OllamaPullResponse(
            status=result["status"],
            base_url=resolved_base_url,
            model=result["model"],
        )
    except OllamaClientError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/query", response_model=QueryResponse)
def query(
    request: QueryRequest,
    settings: AppSettings = Depends(get_settings),
):
    try:
        llm_settings = build_runtime_llm_settings(
            settings.default_llm,
            request.model.model_dump(exclude_none=True) if request.model else None,
        )
        result = get_answer_chain().answer(
            request.question,
            source_filters=request.sources,
            language_filters=request.languages,
            top_k=request.top_k,
            user_role=request.user_role,
            system_context=request.system.model_dump(exclude_none=True) if request.system else None,
            llm_settings=llm_settings,
        )
        return result.to_dict()
    except StoreDependencyError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Query failed: {exc}") from exc


@router.get("/systems", response_model=list[AISystemResponse])
def list_systems():
    try:
        return [item.model_dump() for item in get_system_store().list_systems()]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not load AI systems: {exc}") from exc


@router.get("/systems/export", response_model=list[AISystemResponse])
def export_systems():
    try:
        return [item.model_dump() for item in get_system_store().list_systems()]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not export AI systems: {exc}") from exc


@router.post("/systems/import", response_model=AISystemImportResponse)
def import_systems(request: AISystemImportRequest):
    try:
        store = get_system_store()
        systems = [StoredAISystem.model_validate(item.model_dump()) for item in request.systems]
        result = store.import_systems(
            systems,
            mode=request.mode,
        )
        return AISystemImportResponse(status="ok", mode=request.mode, **result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not import AI systems: {exc}") from exc


@router.post("/systems", response_model=AISystemUpsertResponse)
def upsert_system(request: AISystemUpsertRequest):
    try:
        system, created = get_system_store().upsert_system(
            name=request.name,
            description=request.description,
            system_type=request.system_type,
            catalog=request.catalog or "Default",
        )
        return AISystemUpsertResponse(
            status="ok",
            created=created,
            system=system.model_dump(),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not save AI system: {exc}") from exc


@router.patch("/systems/{system_id}", response_model=AISystemResponse)
def update_system(system_id: str, request: AISystemUpdateRequest):
    try:
        system = get_system_store().update_system(
            system_id,
            name=request.name,
            description=request.description,
            system_type=request.system_type,
            catalog=request.catalog,
        )
        return system.model_dump()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not update AI system: {exc}") from exc


@router.delete("/systems/{system_id}", response_model=AISystemDeleteResponse)
def delete_system(system_id: str):
    try:
        deleted = get_system_store().delete_system(system_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not delete AI system: {exc}") from exc
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Unknown AI system id: {system_id}")
    return AISystemDeleteResponse(status="ok", deleted_system_id=system_id)


@router.post("/systems/analyze", response_model=AISystemAnalysisResponse)
def analyze_systems(
    request: AISystemAnalysisRequest,
    settings: AppSettings = Depends(get_settings),
):
    system_store = get_system_store()
    systems_by_id = {item.id: item for item in system_store.list_systems()}
    missing = [system_id for system_id in request.system_ids if system_id not in systems_by_id]
    if missing:
        raise HTTPException(status_code=404, detail=f"Unknown AI system id(s): {', '.join(missing)}")

    llm_settings = build_runtime_llm_settings(
        settings.default_llm,
        request.model.model_dump(exclude_none=True) if request.model else None,
    )
    analyzer = get_system_analyzer()

    analyzed: list[dict] = []
    skipped: list[dict] = []
    failures: list[dict] = []
    for system_id in request.system_ids:
        system = systems_by_id[system_id]
        already_analyzed = system.analysis_status == "analyzed" and system.level_of_risk is not None
        if already_analyzed and not request.force:
            skipped.append(system.model_dump())
            continue

        try:
            result = analyzer.analyze(
                name=system.name,
                description=system.description,
                system_type=system.system_type,
                user_role=request.user_role,
                llm_settings=llm_settings,
            )
            updated = system_store.update_analysis(
                system.id,
                level_of_risk=result.level_of_risk,
                confidence=result.confidence,
                summary=result.summary,
                citations=result.citations,
                user_role=request.user_role,
                provider=llm_settings.provider,
                model=llm_settings.model,
                status="analyzed",
            )
            analyzed.append(updated.model_dump())
        except LLMDependencyError as exc:
            updated = system_store.update_analysis(
                system.id,
                level_of_risk=system.level_of_risk,
                confidence=system.confidence,
                summary=system.analysis_summary,
                citations=system.analysis_citations,
                user_role=request.user_role,
                provider=llm_settings.provider,
                model=llm_settings.model,
                status="error",
                error=str(exc),
            )
            failures.append({"system_id": system.id, "message": str(exc)})
            analyzed.append(updated.model_dump())
        except Exception as exc:
            updated = system_store.update_analysis(
                system.id,
                level_of_risk=system.level_of_risk,
                confidence=system.confidence,
                summary=system.analysis_summary,
                citations=system.analysis_citations,
                user_role=request.user_role,
                provider=llm_settings.provider,
                model=llm_settings.model,
                status="error",
                error=str(exc),
            )
            failures.append({"system_id": system.id, "message": str(exc)})
            analyzed.append(updated.model_dump())

    return AISystemAnalysisResponse(
        status="ok",
        analyzed=analyzed,
        skipped=skipped,
        failures=failures,
    )


@router.post("/ingest", response_model=IngestResponse)
def ingest(
    request: IngestRequest,
    settings: AppSettings = Depends(get_settings),
):
    parser = LegalDocumentParser()
    try:
        chunks = parser.parse_pdf(
            Path(request.pdf_path),
            source=request.source,
            language=request.language,
        )
        questions = []
        if request.generate_hypothetical_questions:
            llm_settings = build_runtime_llm_settings(
                settings.default_llm,
                request.model.model_dump(exclude_none=True) if request.model else None,
            )
            question_generator = HyPEGenerator(LiteLLMClient(llm_settings))
            questions = question_generator.generate_for_chunks(chunks)
        ingest_result = get_store().ingest(chunks, questions)
        return IngestResponse(
            status="ok",
            pdf_path=request.pdf_path,
            source=request.source,
            language=request.language or chunks[0].language,
            chunk_count=ingest_result["chunks"],
            hypothetical_question_count=ingest_result["hypothetical_questions"],
        )
    except (LLMDependencyError, ParserDependencyError, StoreDependencyError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ingest failed: {exc}") from exc


@router.delete("/sources/{source_id}", response_model=DeleteSourceResponse)
def delete_source(source_id: str):
    try:
        get_store().delete_source(source_id)
        return DeleteSourceResponse(status="ok", deleted_source=source_id)
    except StoreDependencyError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
