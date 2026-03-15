"""Hybrid legal retriever with sparse+dense fusion, reranking, and confidence scoring."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any, Sequence

from ingestion.models import DocumentChunk
from ingestion.store import StoreDependencyError
from retrieval.bm25 import BM25Hit, BM25Index


@dataclass(slots=True)
class RetrievalHit:
    chunk: DocumentChunk
    score: float
    fusion_score: float
    sparse_rank: int | None = None
    dense_rank: int | None = None
    rerank_score: float | None = None
    matched_record_type: str = "chunk"
    matched_text: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.chunk.id,
            "label": self.chunk.label(),
            "source": self.chunk.source,
            "language": self.chunk.language,
            "chunk_type": self.chunk.chunk_type,
            "page_start": self.chunk.page_start,
            "page_end": self.chunk.page_end,
            "article_number": self.chunk.article_number,
            "article_title": self.chunk.article_title,
            "recital_number": self.chunk.recital_number,
            "annex_number": self.chunk.annex_number,
            "score": self.score,
            "fusion_score": self.fusion_score,
            "sparse_rank": self.sparse_rank,
            "dense_rank": self.dense_rank,
            "rerank_score": self.rerank_score,
            "matched_record_type": self.matched_record_type,
            "matched_text": self.matched_text,
            "text": self.chunk.text,
        }


@dataclass(slots=True)
class RetrievalResult:
    query: str
    hits: list[RetrievalHit]
    confidence: float
    low_confidence: bool
    warning: str | None = None
    debug: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "confidence": self.confidence,
            "low_confidence": self.low_confidence,
            "warning": self.warning,
            "debug": self.debug,
            "hits": [hit.to_dict() for hit in self.hits],
        }


class HybridRetriever:
    """Hybrid BM25+dense retriever with optional cross-encoder reranking."""

    def __init__(
        self,
        store: object,
        *,
        bm25_index: BM25Index | None = None,
        rrf_k: int = 60,
        sparse_limit: int = 20,
        dense_limit: int = 20,
        rerank_input_limit: int = 20,
        reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        confidence_threshold: float = 0.45,
    ) -> None:
        self.store = store
        self.bm25_index = bm25_index
        self.rrf_k = rrf_k
        self.sparse_limit = sparse_limit
        self.dense_limit = dense_limit
        self.rerank_input_limit = rerank_input_limit
        self.reranker_model_name = reranker_model
        self.confidence_threshold = confidence_threshold
        self._reranker = None
        self._reranker_unavailable = False
        self._dense_unavailable = False

    def retrieve(
        self,
        query: str,
        *,
        top_k: int = 5,
        source_filters: Sequence[str] | None = None,
        language_filters: Sequence[str] | None = None,
    ) -> RetrievalResult:
        sparse_hits = self._get_sparse_hits(
            query,
            source_filters=source_filters,
            language_filters=language_filters,
        )
        dense_hits = self._get_dense_hits(
            query,
            source_filters=source_filters,
            language_filters=language_filters,
        )
        fused_hits = self._fuse_hits(sparse_hits, dense_hits)
        reranked_hits = self._rerank(query, fused_hits)[:top_k]
        confidence = self._score_confidence(reranked_hits, sparse_hits, dense_hits)
        low_confidence = confidence < self.confidence_threshold
        warning = (
            "Low retrieval confidence. Verify the cited provisions and consider rephrasing the query."
            if low_confidence
            else None
        )

        return RetrievalResult(
            query=query,
            hits=reranked_hits,
            confidence=confidence,
            low_confidence=low_confidence,
            warning=warning,
            debug={
                "sparse_candidates": len(sparse_hits),
                "dense_candidates": len(dense_hits),
                "fused_candidates": len(fused_hits),
                "dense_enabled": not self._dense_unavailable,
                "reranker_enabled": not self._reranker_unavailable,
            },
        )

    def _get_sparse_hits(
        self,
        query: str,
        *,
        source_filters: Sequence[str] | None,
        language_filters: Sequence[str] | None,
    ) -> list[BM25Hit]:
        index = self.bm25_index
        if index is None or source_filters or language_filters:
            index = BM25Index.from_store(
                self.store,
                source_filters=source_filters,
                language_filters=language_filters,
            )
        return index.search(query, limit=self.sparse_limit)

    def _get_dense_hits(
        self,
        query: str,
        *,
        source_filters: Sequence[str] | None,
        language_filters: Sequence[str] | None,
    ) -> list[RetrievalHit]:
        try:
            raw_hits = self.store.query_dense(
                query,
                top_k=self.dense_limit,
                source_filters=source_filters,
                language_filters=language_filters,
                record_types=("chunk", "hype_question"),
            )
        except StoreDependencyError:
            self._dense_unavailable = True
            return []
        if not raw_hits:
            return []

        parent_ids = [
            hit["metadata"].get("parent_chunk_id")
            for hit in raw_hits
            if hit["metadata"].get("record_type") == "hype_question"
        ]
        parent_chunks = self.store.get_chunks_by_ids(parent_ids)

        best_by_chunk: dict[str, RetrievalHit] = {}
        for rank, raw_hit in enumerate(raw_hits, start=1):
            metadata = raw_hit.get("metadata", {})
            record_type = metadata.get("record_type", "chunk")
            if record_type == "hype_question":
                chunk = parent_chunks.get(metadata.get("parent_chunk_id", ""))
            else:
                chunk = DocumentChunk.from_store_record(raw_hit["id"], raw_hit["document"], metadata)
            if chunk is None:
                continue

            score = 1.0 / (1.0 + max(raw_hit.get("distance", 0.0), 0.0))
            candidate = RetrievalHit(
                chunk=chunk,
                score=score,
                fusion_score=0.0,
                dense_rank=rank,
                matched_record_type=record_type,
                matched_text=raw_hit.get("document"),
            )
            existing = best_by_chunk.get(chunk.id)
            if existing is None or candidate.score > existing.score:
                best_by_chunk[chunk.id] = candidate

        return sorted(best_by_chunk.values(), key=lambda hit: hit.score, reverse=True)

    def _fuse_hits(self, sparse_hits: Sequence[BM25Hit], dense_hits: Sequence[RetrievalHit]) -> list[RetrievalHit]:
        fused: dict[str, RetrievalHit] = {}

        for hit in sparse_hits:
            score = 1.0 / (self.rrf_k + hit.rank)
            current = fused.get(hit.chunk.id)
            if current is None:
                fused[hit.chunk.id] = RetrievalHit(
                    chunk=hit.chunk,
                    score=score,
                    fusion_score=score,
                    sparse_rank=hit.rank,
                )
            else:
                current.fusion_score += score
                current.score = current.fusion_score
                current.sparse_rank = hit.rank

        for rank, hit in enumerate(dense_hits, start=1):
            score = 1.0 / (self.rrf_k + rank)
            current = fused.get(hit.chunk.id)
            if current is None:
                fused[hit.chunk.id] = RetrievalHit(
                    chunk=hit.chunk,
                    score=score,
                    fusion_score=score,
                    dense_rank=hit.dense_rank,
                    matched_record_type=hit.matched_record_type,
                    matched_text=hit.matched_text,
                )
            else:
                current.fusion_score += score
                current.score = current.fusion_score
                current.dense_rank = hit.dense_rank
                if hit.matched_record_type == "hype_question":
                    current.matched_record_type = hit.matched_record_type
                    current.matched_text = hit.matched_text

        return sorted(fused.values(), key=lambda hit: hit.fusion_score, reverse=True)

    def _rerank(self, query: str, hits: Sequence[RetrievalHit]) -> list[RetrievalHit]:
        if not hits:
            return []

        reranker = self._load_reranker()
        if reranker is None:
            return sorted(hits, key=lambda hit: hit.fusion_score, reverse=True)

        rerank_candidates = list(hits[: self.rerank_input_limit])
        pairs = [(query, hit.chunk.text) for hit in rerank_candidates]
        scores = reranker.predict(pairs)
        for hit, score in zip(rerank_candidates, scores):
            hit.rerank_score = float(score)
            hit.score = float(score)

        reranked = sorted(rerank_candidates, key=lambda hit: hit.rerank_score or float("-inf"), reverse=True)
        if len(hits) > len(reranked):
            reranked.extend(hits[len(reranked) :])
        return reranked

    def _load_reranker(self) -> Any | None:
        if self._reranker_unavailable:
            return None
        if self._reranker is not None:
            return self._reranker
        try:
            from sentence_transformers import CrossEncoder
        except ImportError:
            self._reranker_unavailable = True
            return None

        try:
            self._reranker = CrossEncoder(
                self.reranker_model_name,
                local_files_only=True,
            )
        except Exception:
            self._reranker_unavailable = True
            return None
        return self._reranker

    def _score_confidence(
        self,
        hits: Sequence[RetrievalHit],
        sparse_hits: Sequence[BM25Hit],
        dense_hits: Sequence[RetrievalHit],
    ) -> float:
        if not hits:
            return 0.0

        top_hit = hits[0]
        top_ids_sparse = {hit.chunk.id for hit in sparse_hits[:5]}
        top_ids_dense = {hit.chunk.id for hit in dense_hits[:5]}
        agreement = len(top_ids_sparse & top_ids_dense) / max(1, min(5, len(top_ids_sparse | top_ids_dense)))

        if top_hit.rerank_score is not None:
            top_signal = 1.0 / (1.0 + math.exp(-top_hit.rerank_score / 6.0))
            second_score = hits[1].rerank_score if len(hits) > 1 and hits[1].rerank_score is not None else 0.0
            margin = 1.0 / (1.0 + math.exp(-(top_hit.rerank_score - second_score)))
        else:
            top_signal = min(top_hit.fusion_score / 0.05, 1.0)
            second_score = hits[1].fusion_score if len(hits) > 1 else 0.0
            margin = min(max(top_hit.fusion_score - second_score, 0.0) / 0.02, 1.0)

        evidence = min(len(hits) / 5.0, 1.0)
        confidence = (0.5 * top_signal) + (0.3 * agreement) + (0.2 * margin * evidence)
        return round(min(max(confidence, 0.0), 1.0), 3)
