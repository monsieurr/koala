"""
Hybrid retriever — the core of the retrieval layer.

Pipeline:
  1. BM25 search          → top 20  (exact term matching, article numbers)
  2. Dense search         → top 20  (semantic similarity via ChromaDB)
  3. RRF fusion           → merged top 20
  4. Cross-encoder rerank → top 5
  5. CRAG confidence      → score + low-confidence flag
  6. Parent expansion     → return full article text to the generation layer

The retriever is the primary interface used by the generation layer (chain.py)
and by the Streamlit UI.
"""

import logging
import math
from dataclasses import dataclass, field
from typing import Optional

from sentence_transformers import CrossEncoder

from ingestion.store import DEFAULT_DB_PATH, DocumentStore
from retrieval.bm25 import BM25Index

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────

DEFAULT_RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
CRAG_LOW_CONFIDENCE_THRESHOLD = 0.2  # Below this reranker score → warn user
RRF_K = 60  # Standard RRF constant


# ── Result types ──────────────────────────────────────────────────────────


@dataclass
class RetrievedChunk:
    """A single retrieval result, enriched with scores and metadata."""
    id: str
    text: str
    metadata: dict
    rrf_score: float = 0.0
    rerank_score: float = 0.0
    crag_score: float = 0.0


@dataclass
class RetrievalResult:
    """The full output of a retrieval call, passed to the generation layer."""
    chunks: list[RetrievedChunk] = field(default_factory=list)
    low_confidence: bool = False
    confidence_score: float = 1.0
    query: str = ""

    @property
    def context_text(self) -> str:
        """Concatenated chunk texts for inclusion in the LLM prompt."""
        parts = []
        for chunk in self.chunks:
            label = chunk.metadata.get("display_label", chunk.id)
            source = chunk.metadata.get("source", "")
            parts.append(f"[{source} — {label}]\n{chunk.text}")
        return "\n\n---\n\n".join(parts)


# ── RRF fusion ─────────────────────────────────────────────────────────────


def reciprocal_rank_fusion(
    *ranked_lists: list[dict],
    k: int = RRF_K,
) -> list[tuple[str, float]]:
    """
    Merge multiple ranked lists using Reciprocal Rank Fusion.

    Args:
        *ranked_lists : Each list is a ranked list of dicts with an "id" key.
        k             : RRF constant (default 60, standard value).

    Returns:
        List of (id, rrf_score) tuples, sorted descending by score.
    """
    scores: dict[str, float] = {}
    for ranked in ranked_lists:
        for rank, item in enumerate(ranked, start=1):
            item_id = item["id"]
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + rank)

    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


# ── Retriever ──────────────────────────────────────────────────────────────


class Retriever:
    """
    Hybrid retriever with BM25, dense search, RRF, cross-encoder reranking,
    and CRAG confidence scoring.
    """

    def __init__(
        self,
        store: Optional[DocumentStore] = None,
        reranker_model: str = DEFAULT_RERANKER_MODEL,
        bm25_top_k: int = 20,
        dense_top_k: int = 20,
        rrf_top_k: int = 20,
        final_top_k: int = 5,
    ):
        """
        Initialise the retriever.

        Args:
            store          : DocumentStore instance. Created with defaults if None.
            reranker_model : HuggingFace model ID for the cross-encoder.
            bm25_top_k     : Candidates from BM25.
            dense_top_k    : Candidates from dense search.
            rrf_top_k      : Candidates after RRF fusion.
            final_top_k    : Final chunks returned after reranking.
        """
        self.store = store or DocumentStore(db_path=DEFAULT_DB_PATH)
        self.bm25_top_k = bm25_top_k
        self.dense_top_k = dense_top_k
        self.rrf_top_k = rrf_top_k
        self.final_top_k = final_top_k

        logger.info(f"Loading cross-encoder '{reranker_model}'…")
        self._reranker = CrossEncoder(reranker_model)

        # Build BM25 index from current store contents
        self._bm25: Optional[BM25Index] = None
        self._rebuild_bm25()

    def _rebuild_bm25(self) -> None:
        """(Re)build BM25 index from ChromaDB. Call after ingesting new documents."""
        all_chunks = self.store.get_all(include_hype=False)
        if not all_chunks:
            logger.warning("Store is empty — BM25 index not built.")
            self._bm25 = None
            return
        self._bm25 = BM25Index(all_chunks)

    # ── Main retrieval method ──────────────────────────────────────────────

    def retrieve(
        self,
        query: str,
        source: Optional[str] = None,
        language: Optional[str] = None,
        chunk_type: Optional[str] = None,
    ) -> RetrievalResult:
        """
        Run the full retrieval pipeline for a user query.

        Args:
            query      : Natural language question.
            source     : Filter by document source (e.g. "AI Act").
            language   : Filter by language code (e.g. "en").
            chunk_type : Filter by chunk type ("article" | "recital" | "annex").

        Returns:
            RetrievalResult with ranked chunks and confidence metadata.
        """
        if self._bm25 is None:
            self._rebuild_bm25()
            if self._bm25 is None:
                logger.error("No documents in store. Please ingest documents first.")
                return RetrievalResult(query=query, low_confidence=True, confidence_score=0.0)

        # Build metadata filter using $and-aware helper
        raw_filters: dict = {}
        if source:
            raw_filters["source"] = source
        if language:
            raw_filters["language"] = language
        if chunk_type:
            raw_filters["chunk_type"] = chunk_type
        from ingestion.store import DocumentStore as _DS
        where = _DS.build_chroma_where(raw_filters)

        # ── Step 1: BM25 search ────────────────────────────────────────────
        bm25_results = self._bm25.search(query, n=self.bm25_top_k, where=where)
        logger.debug(f"BM25 returned {len(bm25_results)} results")

        # ── Step 2: Dense search ───────────────────────────────────────────
        dense_results = self.store.query(query, n_results=self.dense_top_k, where=where)
        logger.debug(f"Dense search returned {len(dense_results)} results")

        # ── Step 3: RRF fusion ─────────────────────────────────────────────
        fused = reciprocal_rank_fusion(bm25_results, dense_results)
        fused_ids = [item_id for item_id, _ in fused[: self.rrf_top_k]]
        fused_scores = {item_id: score for item_id, score in fused[: self.rrf_top_k]}

        # Resolve HyPE parent IDs — if a HyPE entry made it through, use parent
        fused_ids = self._resolve_parent_ids(fused_ids)

        # Deduplicate while preserving order
        seen: set[str] = set()
        unique_ids: list[str] = []
        for chunk_id in fused_ids:
            if chunk_id not in seen:
                seen.add(chunk_id)
                unique_ids.append(chunk_id)

        # Fetch full chunk data for unique IDs
        candidates = self._fetch_chunks(unique_ids, bm25_results, dense_results)

        if not candidates:
            return RetrievalResult(query=query, low_confidence=True, confidence_score=0.0)

        # Assign RRF scores
        for chunk in candidates:
            chunk.rrf_score = fused_scores.get(chunk.id, 0.0)

        # ── Step 4: Cross-encoder reranking ────────────────────────────────
        candidates = self._rerank(query, candidates)
        top_chunks = candidates[: self.final_top_k]

        # ── Step 5: CRAG confidence scoring ───────────────────────────────
        confidence_score = self._crag_score(top_chunks)
        low_confidence = confidence_score < CRAG_LOW_CONFIDENCE_THRESHOLD

        if low_confidence:
            logger.warning(
                f"Low retrieval confidence ({confidence_score:.3f}) for query: '{query}'"
            )

        return RetrievalResult(
            chunks=top_chunks,
            low_confidence=low_confidence,
            confidence_score=confidence_score,
            query=query,
        )

    # ── Internal helpers ───────────────────────────────────────────────────

    def _resolve_parent_ids(self, ids: list[str]) -> list[str]:
        """Replace HyPE question IDs with their parent article IDs."""
        resolved = []
        for chunk_id in ids:
            if "_hype_" in chunk_id:
                parent_id = chunk_id.rsplit("_hype_", 1)[0]
                resolved.append(parent_id)
            else:
                resolved.append(chunk_id)
        return resolved

    def _fetch_chunks(
        self,
        ids: list[str],
        bm25_results: list[dict],
        dense_results: list[dict],
    ) -> list[RetrievedChunk]:
        """
        Fetch full chunk data for a list of IDs.
        First looks in the already-fetched BM25/dense results, then falls back
        to the store for any IDs not found there.
        """
        # Build a lookup from the already-fetched results
        cache: dict[str, dict] = {}
        for r in bm25_results + dense_results:
            cache[r["id"]] = r

        chunks = []
        for chunk_id in ids:
            if chunk_id in cache:
                r = cache[chunk_id]
                chunks.append(
                    RetrievedChunk(
                        id=chunk_id,
                        text=r["text"],
                        metadata=r["metadata"],
                    )
                )
            else:
                # Fetch from store (e.g. HyPE parent not in top-20)
                r = self.store.get_by_id(chunk_id)
                if r:
                    chunks.append(
                        RetrievedChunk(id=chunk_id, text=r["text"], metadata=r["metadata"])
                    )

        return chunks

    def _rerank(self, query: str, candidates: list[RetrievedChunk]) -> list[RetrievedChunk]:
        """Score all candidates with the cross-encoder and sort descending.
        If the reranker fails (e.g. model not loaded), falls back to RRF order.
        Text is truncated to 512 tokens (not characters) for the cross-encoder."""
        if not candidates:
            return candidates

        try:
            # Use tokenizer max_length to truncate properly at token level,
            # not the naive [:512] char slice which cuts mid-sentence.
            pairs = [(query, c.text) for c in candidates]
            scores = self._reranker.predict(
                pairs,
                apply_softmax=False,
                convert_to_numpy=True,
            ).tolist()

            for chunk, score in zip(candidates, scores):
                chunk.rerank_score = float(score)

            candidates.sort(key=lambda c: c.rerank_score, reverse=True)
        except Exception as e:
            logger.warning(f"Cross-encoder reranking failed, using RRF order: {e}")
            # Fallback: use RRF scores as a proxy for rank
            for chunk in candidates:
                chunk.rerank_score = chunk.rrf_score

        return candidates

    @staticmethod
    def _crag_score(chunks: list[RetrievedChunk]) -> float:
        """
        Lightweight CRAG confidence score.

        Uses the sigmoid-normalised reranker score of the top result as a
        proxy for retrieval confidence. Returns a value in [0, 1].

        A score below CRAG_LOW_CONFIDENCE_THRESHOLD triggers a warning to the user.
        """
        if not chunks:
            return 0.0

        top_score = chunks[0].rerank_score
        # Sigmoid normalisation: maps raw cross-encoder scores to (0, 1)
        normalised = 1.0 / (1.0 + math.exp(-top_score))
        chunks[0].crag_score = normalised
        return normalised
