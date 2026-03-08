"""
BM25 sparse index for hybrid retrieval.

BM25 is essential for legal text because:
- Article numbers ("Article 6", "Article 22") are exact-match queries
- Legal terms of art have precise meanings that semantic search may miss
- EU regulations use consistent terminology that BM25 handles well

The index is built in-memory at query time from the ChromaDB collection.
It is rebuilt on each retriever initialisation (fast — typically < 1s).
"""

import logging
import re
from typing import Optional

from rank_bm25 import BM25Okapi

logger = logging.getLogger(__name__)

# ── Tokeniser ──────────────────────────────────────────────────────────────


def tokenise(text: str) -> list[str]:
    """
    Simple whitespace + punctuation tokeniser, lowercased.
    Preserves hyphenated terms (e.g. 'high-risk') as single tokens.
    """
    text = text.lower()
    # Split on whitespace and most punctuation, but keep hyphens inside words
    tokens = re.split(r"[^\w\-]+", text)
    return [t for t in tokens if len(t) > 1]


# ── BM25 index ─────────────────────────────────────────────────────────────


class BM25Index:
    """
    In-memory BM25 index over all document chunks.

    Attributes:
        chunks    : The raw chunk dicts from DocumentStore.get_all()
        bm25      : The BM25Okapi instance
    """

    def __init__(self, chunks: list[dict]):
        """
        Build the index from a list of chunk dicts (as returned by DocumentStore).

        Args:
            chunks: List of {"id": ..., "text": ..., "metadata": ...} dicts.
        """
        if not chunks:
            raise ValueError("Cannot build BM25 index from empty chunk list.")

        self.chunks = chunks
        corpus = [tokenise(c["text"]) for c in chunks]
        self.bm25 = BM25Okapi(corpus)
        logger.info(f"BM25 index built over {len(chunks)} chunks.")

    def search(self, query: str, n: int = 20, where: Optional[dict] = None) -> list[dict]:
        """
        Search the BM25 index.

        Args:
            query : Natural language query string.
            n     : Maximum number of results to return.
            where : Optional metadata filter dict (e.g. {"language": "en"}).
                    Applied post-scoring, so all chunks are scored but only
                    matching ones are returned.

        Returns:
            List of result dicts: {"id", "text", "metadata", "bm25_score"}
            sorted by BM25 score descending.
        """
        tokens = tokenise(query)
        if not tokens:
            return []

        scores = self.bm25.get_scores(tokens)

        # Pair each chunk with its score
        scored = [
            (score, chunk)
            for score, chunk in zip(scores, self.chunks)
            if score > 0
        ]

        # Apply metadata filter
        if where:
            scored = [
                (score, chunk)
                for score, chunk in scored
                if _matches_filter(chunk["metadata"], where)
            ]

        # Sort descending and take top-n
        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:n]

        return [
            {
                "id": chunk["id"],
                "text": chunk["text"],
                "metadata": chunk["metadata"],
                "bm25_score": float(score),
            }
            for score, chunk in top
        ]


def _matches_filter(metadata: dict, where: dict) -> bool:
    """
    Return True if all conditions in where match the metadata dict.
    Handles ChromaDB's $and compound filter syntax produced by
    DocumentStore.build_chroma_where() for multi-key filters.
    """
    if "$and" in where:
        return all(_matches_filter(metadata, clause) for clause in where["$and"])
    if "$or" in where:
        return any(_matches_filter(metadata, clause) for clause in where["$or"])
    for key, value in where.items():
        if metadata.get(key) != value:
            return False
    return True
