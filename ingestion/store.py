"""
ChromaDB storage layer.

Handles:
- Initialising and persisting the ChromaDB collection
- Embedding chunks with sentence-transformers (local, no API needed)
- Upserting, querying, and deleting chunks
- Returning raw metadata and documents for the retrieval layer
"""

import logging
from pathlib import Path
from typing import Optional

import chromadb
from chromadb import Collection
from sentence_transformers import SentenceTransformer

from ingestion.models import DocumentChunk, Language

logger = logging.getLogger(__name__)

# ── Defaults ──────────────────────────────────────────────────────────────

DEFAULT_EMBED_MODEL = "sentence-transformers/multi-qa-mpnet-base-dot-v1"
DEFAULT_COLLECTION = "eu_legal_docs"
DEFAULT_DB_PATH = Path("data/chroma")

# ── Store class ───────────────────────────────────────────────────────────


class DocumentStore:
    """
    Thin wrapper around ChromaDB providing embed-and-store for DocumentChunks.

    Uses a single collection for all documents and languages, differentiating
    via metadata filters (source, language, chunk_type).
    """

    def __init__(
        self,
        db_path: Path = DEFAULT_DB_PATH,
        collection_name: str = DEFAULT_COLLECTION,
        embed_model: str = DEFAULT_EMBED_MODEL,
    ):
        self.db_path = Path(db_path)
        self.db_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"Loading embedding model '{embed_model}'…")
        self._embedder = SentenceTransformer(embed_model)

        self._client = chromadb.PersistentClient(path=str(self.db_path))
        self._collection: Collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            f"ChromaDB ready at '{self.db_path}' "
            f"({self._collection.count()} chunks stored)"
        )

    # ── Embedding ──────────────────────────────────────────────────────────

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of strings and return float vectors."""
        return self._embedder.encode(texts, show_progress_bar=False).tolist()

    # ── Write ──────────────────────────────────────────────────────────────

    def upsert_chunks(self, chunks: list[DocumentChunk], batch_size: int = 64) -> None:
        """
        Embed and upsert chunks into ChromaDB.
        Existing chunks with the same ID are overwritten (safe to re-run).
        """
        if not chunks:
            logger.warning("upsert_chunks called with empty list — nothing to do.")
            return

        logger.info(f"Upserting {len(chunks)} chunks in batches of {batch_size}…")
        # Guard: ChromaDB rejects batches with duplicate IDs; deduplicate up-front
        # (last write wins — matches ChromaDB's own upsert semantics).
        seen: dict[str, DocumentChunk] = {}
        for c in chunks:
            seen[c.id] = c
        if len(seen) < len(chunks):
            logger.warning(
                f"Removed {len(chunks) - len(seen)} duplicate chunk ID(s) before upsert"
            )
        chunks = list(seen.values())
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            texts = [c.text for c in batch]
            try:
                embeddings = self.embed(texts)
                self._collection.upsert(
                    ids=[c.id for c in batch],
                    embeddings=embeddings,
                    documents=texts,
                    metadatas=[c.metadata_dict() for c in batch],
                )
                logger.debug(f"  Batch {i // batch_size + 1}: upserted {len(batch)} chunks")
            except Exception as e:
                logger.error(f"  Batch {i // batch_size + 1} failed: {e}")
                raise RuntimeError(f"Failed to upsert batch starting at index {i}: {e}") from e

        logger.info("Upsert complete.")

    def upsert_hypothetical_questions(
        self,
        chunk_id: str,
        questions: list[str],
    ) -> None:
        """
        Store HyPE hypothetical question embeddings alongside an article chunk.
        Each question is stored as a separate entry with ID '{chunk_id}_hype_{n}'.
        """
        if not questions:
            return

        embeddings = self.embed(questions)
        ids = [f"{chunk_id}_hype_{i}" for i in range(len(questions))]

        # Fetch the parent chunk's metadata to propagate it
        result = self._collection.get(ids=[chunk_id], include=["metadatas"])
        if not result["metadatas"]:
            logger.warning(f"Parent chunk '{chunk_id}' not found — skipping HyPE upsert.")
            return

        parent_meta = dict(result["metadatas"][0])
        parent_meta["is_hype"] = True
        parent_meta["parent_id"] = chunk_id

        self._collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=questions,
            metadatas=[{**parent_meta, "hype_question": q} for q in questions],
        )

    # ── Read ───────────────────────────────────────────────────────────────

    @staticmethod
    def build_chroma_where(filters: dict) -> Optional[dict]:
        """
        Convert a flat filter dict to a ChromaDB-compatible where clause.

        ChromaDB requires the $and operator when filtering by more than one key.
        A single-key dict works as-is; multiple keys must be wrapped in $and.

        Examples:
          {"source": "AI Act"}                       → {"source": "AI Act"}
          {"source": "AI Act", "language": "en"}     → {"$and": [{"source": "AI Act"}, {"language": "en"}]}
        """
        if not filters:
            return None
        items = [{k: v} for k, v in filters.items() if v is not None]
        if not items:
            return None
        if len(items) == 1:
            return items[0]
        return {"$and": items}

    def query(
        self,
        query_text: str,
        n_results: int = 20,
        where: Optional[dict] = None,
    ) -> list[dict]:
        """
        Dense semantic search. Returns up to n_results results as dicts with
        keys: id, text, metadata, distance.

        `where` must already be a ChromaDB-compatible filter (use build_chroma_where).
        """
        try:
            embedding = self.embed([query_text])[0]
            count = self._collection.count()
            if count == 0:
                return []

            kwargs: dict = {
                "query_embeddings": [embedding],
                "n_results": min(n_results, max(1, count)),
                "include": ["documents", "metadatas", "distances"],
            }
            if where:
                kwargs["where"] = where

            result = self._collection.query(**kwargs)

            hits = []
            for doc, meta, dist in zip(
                result["documents"][0],
                result["metadatas"][0],
                result["distances"][0],
            ):
                hits.append({"id": meta.get("id", ""), "text": doc, "metadata": meta, "distance": dist})

            return hits
        except Exception as e:
            logger.error(f"Dense query failed: {e}")
            return []

    def get_by_id(self, chunk_id: str) -> Optional[dict]:
        """Fetch a single chunk by its ID. Returns None if not found."""
        try:
            result = self._collection.get(ids=[chunk_id], include=["documents", "metadatas"])
            if not result["ids"]:
                return None
            return {
                "id": chunk_id,
                "text": result["documents"][0],
                "metadata": result["metadatas"][0],
            }
        except Exception as e:
            logger.error(f"get_by_id failed for '{chunk_id}': {e}")
            return None

    def get_all(
        self,
        where: Optional[dict] = None,
        include_hype: bool = False,
    ) -> list[dict]:
        """
        Return all chunks (optionally filtered). Used to build the BM25 index.
        Set include_hype=False (default) to exclude HyPE question entries.

        `where` must already be a ChromaDB-compatible filter (use build_chroma_where).

        Bug fixed vs V1: HyPE filtering is always applied post-fetch regardless
        of whether a `where` filter is also present.
        """
        try:
            count = self._collection.count()
            if count == 0:
                return []

            kwargs: dict = {"include": ["documents", "metadatas"], "limit": count}
            if where:
                kwargs["where"] = where

            result = self._collection.get(**kwargs)

            hits = []
            for doc, meta in zip(result["documents"], result["metadatas"]):
                # Always filter HyPE entries unless explicitly requested
                if not include_hype and meta.get("is_hype"):
                    continue
                hits.append({"id": meta.get("id", ""), "text": doc, "metadata": meta})

            return hits
        except Exception as e:
            logger.error(f"get_all failed: {e}")
            return []

    # ── Delete ─────────────────────────────────────────────────────────────

    def delete_by_source(self, source: str) -> int:
        """Delete all chunks (including HyPE entries) for a given source document."""
        try:
            result = self._collection.get(
                where={"source": source},
                include=[],
            )
            ids = result["ids"]
            if ids:
                self._collection.delete(ids=ids)
            logger.info(f"Deleted {len(ids)} chunks for source '{source}'")
            return len(ids)
        except Exception as e:
            logger.error(f"delete_by_source failed for '{source}': {e}")
            raise RuntimeError(f"Failed to delete source '{source}': {e}") from e

    def list_sources(self) -> list[dict]:
        """
        Return a deduplicated list of ingested sources with their languages.
        Efficient alternative to calling get_all() just to read source names.
        Returns list of {"source": str, "language": str} dicts.
        """
        stats = self.stats()
        sources = []
        for key in stats["by_source"]:
            # key format: "AI Act (en)"
            try:
                source, lang = key.rsplit(" (", 1)
                lang = lang.rstrip(")")
            except ValueError:
                source, lang = key, ""
            sources.append({"source": source, "language": lang, "key": key})
        return sources

    # ── Stats ──────────────────────────────────────────────────────────────

    def stats(self) -> dict:
        """Return a summary of what's stored in the collection."""
        try:
            all_chunks = self.get_all(include_hype=False)
            sources: dict[str, dict] = {}

            for chunk in all_chunks:
                meta = chunk["metadata"]
                key = f"{meta.get('source', '?')} ({meta.get('language', '?')})"
                if key not in sources:
                    sources[key] = {"article": 0, "recital": 0, "annex": 0, "total": 0}
                ctype = meta.get("chunk_type", "unknown")
                sources[key][ctype] = sources[key].get(ctype, 0) + 1
                sources[key]["total"] += 1

            return {
                "total_chunks": self._collection.count(),
                "real_chunks": len(all_chunks),
                "by_source": sources,
            }
        except Exception as e:
            logger.error(f"stats() failed: {e}")
            return {"total_chunks": 0, "real_chunks": 0, "by_source": {}}