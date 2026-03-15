"""Sparse retrieval utilities built from persisted document chunks."""

from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Iterable, Sequence

from ingestion.models import DocumentChunk


_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9]+(?:[./-][A-Za-z0-9]+)*")


def tokenize_legal_text(text: str) -> list[str]:
    return [token.lower() for token in _TOKEN_PATTERN.findall(text)]


def build_sparse_text(chunk: DocumentChunk) -> str:
    fields = [
        chunk.source,
        chunk.language,
        chunk.chunk_type,
        chunk.chapter or "",
        chunk.chapter_title or "",
        chunk.article_number or "",
        chunk.article_title or "",
        str(chunk.metadata.get("section_title", "")),
        chunk.recital_number or "",
        chunk.annex_number or "",
        chunk.text,
    ]
    return "\n".join(field for field in fields if field)


@dataclass(frozen=True, slots=True)
class BM25Hit:
    chunk: DocumentChunk
    score: float
    rank: int


class BM25Index:
    """In-memory BM25 index built from current ChromaDB chunk contents."""

    def __init__(self, chunks: Sequence[DocumentChunk] | None = None) -> None:
        self._chunks: list[DocumentChunk] = []
        self._documents: list[list[str]] = []
        self._bm25 = None
        if chunks:
            self.refresh(chunks)

    @classmethod
    def from_store(
        cls,
        store: object,
        *,
        source_filters: Sequence[str] | None = None,
        language_filters: Sequence[str] | None = None,
    ) -> "BM25Index":
        chunks = store.list_chunks(
            source_filters=source_filters,
            language_filters=language_filters,
            include_questions=False,
        )
        return cls(chunks)

    def refresh(self, chunks: Iterable[DocumentChunk]) -> None:
        chunk_list = [chunk for chunk in chunks if chunk.chunk_type in {"article", "recital", "annex"}]
        self._chunks = chunk_list
        self._documents = [tokenize_legal_text(build_sparse_text(chunk)) for chunk in chunk_list]
        if not self._documents:
            self._bm25 = None
            return

        try:
            from rank_bm25 import BM25Okapi
        except ImportError:
            BM25Okapi = _FallbackBM25Okapi

        self._bm25 = BM25Okapi(self._documents)

    def search(self, query: str, limit: int = 20) -> list[BM25Hit]:
        if not self._bm25 or not self._chunks:
            return []
        tokens = tokenize_legal_text(query)
        if not tokens:
            return []
        scores = self._bm25.get_scores(tokens)
        ranked = sorted(
            enumerate(scores),
            key=lambda item: item[1],
            reverse=True,
        )
        hits: list[BM25Hit] = []
        for rank, (index, score) in enumerate(ranked[:limit], start=1):
            if float(score) <= 0:
                continue
            hits.append(BM25Hit(chunk=self._chunks[index], score=float(score), rank=rank))
        return hits


class _FallbackBM25Okapi:
    """Minimal BM25 implementation used when rank_bm25 is unavailable."""

    def __init__(
        self,
        corpus: Sequence[Sequence[str]],
        *,
        k1: float = 1.5,
        b: float = 0.75,
    ) -> None:
        self.corpus = [list(document) for document in corpus]
        self.k1 = k1
        self.b = b
        self.document_lengths = [len(document) for document in self.corpus]
        self.average_document_length = (
            sum(self.document_lengths) / len(self.document_lengths) if self.document_lengths else 0.0
        )

        self.document_frequencies: dict[str, int] = {}
        self.term_frequencies: list[dict[str, int]] = []
        for document in self.corpus:
            frequencies: dict[str, int] = {}
            for token in document:
                frequencies[token] = frequencies.get(token, 0) + 1
            self.term_frequencies.append(frequencies)
            for token in frequencies:
                self.document_frequencies[token] = self.document_frequencies.get(token, 0) + 1

        self.idf: dict[str, float] = {}
        corpus_size = len(self.corpus)
        for token, frequency in self.document_frequencies.items():
            self.idf[token] = math.log(1 + ((corpus_size - frequency + 0.5) / (frequency + 0.5)))

    def get_scores(self, query_tokens: Sequence[str]) -> list[float]:
        scores: list[float] = []
        for index, frequencies in enumerate(self.term_frequencies):
            score = 0.0
            document_length = self.document_lengths[index]
            length_norm = self.k1 * (
                1 - self.b + self.b * (document_length / self.average_document_length if self.average_document_length else 0.0)
            )
            for token in query_tokens:
                term_frequency = frequencies.get(token, 0)
                if term_frequency == 0:
                    continue
                numerator = term_frequency * (self.k1 + 1)
                denominator = term_frequency + length_norm
                score += self.idf.get(token, 0.0) * (numerator / denominator if denominator else 0.0)
            scores.append(score)
        return scores
