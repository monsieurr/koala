"""ChromaDB-backed persistence and embedding helpers."""

from __future__ import annotations

from collections import Counter
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Sequence

from .models import DocumentChunk, HypotheticalQuestion


class StoreDependencyError(RuntimeError):
    """Raised when optional vector-store dependencies are missing."""


class ChromaVectorStore:
    """Thin wrapper around ChromaDB with local sentence-transformer embeddings."""

    def __init__(
        self,
        persist_directory: str | Path = "data/chroma",
        collection_name: str = "legal_documents",
        embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2",
    ) -> None:
        self.persist_directory = Path(persist_directory)
        self.collection_name = collection_name
        self.embedding_model_name = embedding_model
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        self._client = None
        self._collection = None
        self._embedding_model = None
        self._stats_cache: dict[str, Any] | None = None
        self._source_summaries_cache: list[dict[str, Any]] | None = None
        self._cache_dirty = True

    @property
    def client(self) -> Any:
        if self._client is None:
            try:
                import chromadb
                from chromadb.config import Settings
            except ImportError as exc:
                raise StoreDependencyError(
                    "chromadb is required for persistence. Install dependencies from requirements.txt."
                ) from exc

            self._client = chromadb.PersistentClient(
                path=str(self.persist_directory),
                settings=Settings(anonymized_telemetry=False),
            )
        return self._client

    @property
    def collection(self) -> Any:
        if self._collection is None:
            self._collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    @property
    def embedding_model(self) -> Any:
        if self._embedding_model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise StoreDependencyError(
                    "sentence-transformers is required for local embeddings. "
                    "Install dependencies from requirements.txt."
                ) from exc

            try:
                self._embedding_model = SentenceTransformer(
                    self.embedding_model_name,
                    local_files_only=True,
                )
            except Exception:
                try:
                    self._embedding_model = SentenceTransformer(self.embedding_model_name)
                except Exception as exc:
                    raise StoreDependencyError(
                        "The embedding model could not be loaded. If you are using a Hugging Face model name, "
                        "make sure it is already cached locally or allow a one-time download. "
                        f"Model: {self.embedding_model_name}"
                    ) from exc
            except Exception as exc:
                raise StoreDependencyError(
                    "The embedding model could not be loaded. "
                    f"Model: {self.embedding_model_name}"
                ) from exc
        return self._embedding_model

    def upsert_chunks(self, chunks: Sequence[DocumentChunk]) -> int:
        if not chunks:
            return 0
        texts = [chunk.text for chunk in chunks]
        embeddings = self._embed_texts(texts)
        self.collection.upsert(
            ids=[chunk.id for chunk in chunks],
            documents=texts,
            metadatas=[chunk.to_metadata() for chunk in chunks],
            embeddings=embeddings,
        )
        self._mark_dirty()
        return len(chunks)

    def upsert_hypothetical_questions(self, questions: Sequence[HypotheticalQuestion]) -> int:
        if not questions:
            return 0
        texts = [question.text for question in questions]
        embeddings = self._embed_texts(texts)
        self.collection.upsert(
            ids=[question.id for question in questions],
            documents=texts,
            metadatas=[question.to_metadata() for question in questions],
            embeddings=embeddings,
        )
        self._mark_dirty()
        return len(questions)

    def ingest(
        self,
        chunks: Sequence[DocumentChunk],
        hypothetical_questions: Sequence[HypotheticalQuestion] | None = None,
    ) -> dict[str, int]:
        inserted_chunks = self.upsert_chunks(chunks)
        inserted_questions = self.upsert_hypothetical_questions(hypothetical_questions or [])
        return {"chunks": inserted_chunks, "hypothetical_questions": inserted_questions}

    def list_chunks(
        self,
        *,
        source_filters: Sequence[str] | None = None,
        language_filters: Sequence[str] | None = None,
        include_questions: bool = False,
    ) -> list[DocumentChunk]:
        record_types = ["chunk", "hype_question"] if include_questions else ["chunk"]
        raw = self.collection.get(
            where=self._build_where(
                source_filters=source_filters,
                language_filters=language_filters,
                record_types=record_types,
            ),
            include=["documents", "metadatas"],
        )
        chunks: list[DocumentChunk] = []
        for record_id, document, metadata in zip(
            raw.get("ids", []),
            raw.get("documents", []),
            raw.get("metadatas", []),
        ):
            metadata = metadata or {}
            if metadata.get("record_type", "chunk") != "chunk":
                continue
            chunks.append(DocumentChunk.from_store_record(record_id, document, metadata))
        return chunks

    def get_chunks_by_ids(self, chunk_ids: Iterable[str]) -> dict[str, DocumentChunk]:
        ids = list(dict.fromkeys(chunk_ids))
        if not ids:
            return {}
        raw = self.collection.get(ids=ids, include=["documents", "metadatas"])
        return {
            record_id: DocumentChunk.from_store_record(record_id, document, metadata)
            for record_id, document, metadata in zip(
                raw.get("ids", []),
                raw.get("documents", []),
                raw.get("metadatas", []),
            )
            if (metadata or {}).get("record_type", "chunk") == "chunk"
        }

    def query_dense(
        self,
        query: str,
        *,
        top_k: int = 20,
        source_filters: Sequence[str] | None = None,
        language_filters: Sequence[str] | None = None,
        record_types: Sequence[str] | None = None,
    ) -> list[dict[str, Any]]:
        embeddings = self._embed_texts([query])
        results = self.collection.query(
            query_embeddings=embeddings,
            n_results=top_k,
            where=self._build_where(
                source_filters=source_filters,
                language_filters=language_filters,
                record_types=record_types or ("chunk", "hype_question"),
            ),
            include=["documents", "metadatas", "distances"],
        )

        ids = results.get("ids", [[]])[0]
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]
        flattened: list[dict[str, Any]] = []
        for record_id, document, metadata, distance in zip(ids, documents, metadatas, distances):
            flattened.append(
                {
                    "id": record_id,
                    "document": document,
                    "metadata": metadata or {},
                    "distance": float(distance),
                }
            )
        return flattened

    def delete_source(self, source: str) -> None:
        self.collection.delete(where={"source": source})
        self._mark_dirty()

    def stats(self) -> dict[str, Any]:
        self._ensure_cache()
        return dict(self._stats_cache or {})

    def source_summaries(self) -> list[dict[str, Any]]:
        self._ensure_cache()
        return list(self._source_summaries_cache or [])

    def _mark_dirty(self) -> None:
        self._cache_dirty = True

    def _ensure_cache(self) -> None:
        if not self._cache_dirty and self._stats_cache is not None and self._source_summaries_cache is not None:
            return
        self._stats_cache, self._source_summaries_cache = self._rebuild_cache()
        self._cache_dirty = False

    def _rebuild_cache(self) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        raw = self.collection.get(include=["metadatas"])
        metadatas = [metadata or {} for metadata in raw.get("metadatas", [])]

        if not metadatas:
            stats = {
                "collection_name": self.collection_name,
                "persist_directory": str(self.persist_directory),
                "document_count": 0,
                "sources": {},
                "languages": {},
                "chunk_types": {},
                "record_types": {},
            }
            return stats, []

        source_counts = Counter(metadata.get("source", "unknown") for metadata in metadatas)
        language_counts = Counter(metadata.get("language", "unknown") for metadata in metadatas)
        chunk_counts = Counter(metadata.get("chunk_type", "unknown") for metadata in metadatas)
        record_counts = Counter(metadata.get("record_type", "chunk") for metadata in metadatas)
        stats = {
            "collection_name": self.collection_name,
            "persist_directory": str(self.persist_directory),
            "document_count": len(metadatas),
            "sources": dict(source_counts),
            "languages": dict(language_counts),
            "chunk_types": dict(chunk_counts),
            "record_types": dict(record_counts),
        }

        grouped: dict[str, dict[str, Any]] = {}
        chunk_type_counters: dict[str, Counter[str]] = defaultdict(Counter)
        language_sets: dict[str, set[str]] = defaultdict(set)

        for metadata in metadatas:
            item = metadata or {}
            if item.get("record_type", "chunk") != "chunk":
                continue
            source = item.get("source")
            language = item.get("language")
            chunk_type = item.get("chunk_type")
            if not source:
                continue

            grouped.setdefault(
                source,
                {
                    "id": source,
                    "source": source,
                    "chunk_count": 0,
                    "languages": [],
                    "articles": 0,
                    "recitals": 0,
                    "annexes": 0,
                },
            )
            grouped[source]["chunk_count"] += 1
            if language:
                language_sets[source].add(language)
            if chunk_type:
                chunk_type_counters[source][chunk_type] += 1

        for source, summary in grouped.items():
            summary["languages"] = sorted(language_sets[source])
            summary["articles"] = chunk_type_counters[source].get("article", 0)
            summary["recitals"] = chunk_type_counters[source].get("recital", 0)
            summary["annexes"] = chunk_type_counters[source].get("annex", 0)

        summaries = sorted(grouped.values(), key=lambda item: item["source"].lower())
        return stats, summaries

    def _embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        embeddings = self.embedding_model.encode(
            list(texts),
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return embeddings.tolist()

    def _build_where(
        self,
        *,
        source_filters: Sequence[str] | None,
        language_filters: Sequence[str] | None,
        record_types: Sequence[str] | None,
    ) -> dict[str, Any] | None:
        clauses: list[dict[str, Any]] = []
        if source_filters:
            values = list(source_filters)
            clauses.append({"source": values[0]} if len(values) == 1 else {"source": {"$in": values}})
        if language_filters:
            values = list(language_filters)
            clauses.append({"language": values[0]} if len(values) == 1 else {"language": {"$in": values}})
        if record_types:
            values = list(record_types)
            clauses.append({"record_type": values[0]} if len(values) == 1 else {"record_type": {"$in": values}})
        if not clauses:
            return None
        if len(clauses) == 1:
            return clauses[0]
        return {"$and": clauses}
