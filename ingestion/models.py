"""Shared Pydantic models used across ingestion and retrieval."""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ChunkType = Literal["article", "recital", "annex"]
RecordType = Literal["chunk", "hype_question"]


def slugify_fragment(value: str) -> str:
    """Convert a free-form value into a stable ASCII identifier fragment."""
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", normalized.strip().lower())
    return slug.strip("_") or "item"


class DocumentChunk(BaseModel):
    """A single retrievable legal unit such as an article, recital, or annex."""

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    language: str = Field(min_length=2, max_length=5)
    chunk_type: ChunkType
    text: str = Field(min_length=1)
    chapter: str | None = None
    chapter_title: str | None = None
    article_number: str | None = None
    article_title: str | None = None
    recital_number: str | None = None
    annex_number: str | None = None
    page_start: int = Field(ge=1)
    page_end: int = Field(ge=1)
    parent_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_structure(self) -> "DocumentChunk":
        if self.page_end < self.page_start:
            raise ValueError("page_end must be greater than or equal to page_start")

        required = {
            "article": self.article_number,
            "recital": self.recital_number,
            "annex": self.annex_number,
        }
        current = required[self.chunk_type]
        if not current:
            raise ValueError(f"{self.chunk_type} chunks require their matching number field")

        conflicting_fields = {
            "article": ("recital_number", "annex_number"),
            "recital": ("article_number", "annex_number"),
            "annex": ("article_number", "recital_number"),
        }
        for field_name in conflicting_fields[self.chunk_type]:
            if getattr(self, field_name):
                raise ValueError(f"{field_name} must be unset for {self.chunk_type} chunks")
        return self

    def label(self) -> str:
        if self.chunk_type == "article":
            return f"Article {self.article_number}"
        if self.chunk_type == "recital":
            return f"Recital {self.recital_number}"
        return f"Annex {self.annex_number}"

    def to_metadata(self) -> dict[str, Any]:
        base = self.model_dump(exclude={"text", "metadata"})
        merged = {**base, **self.metadata, "record_type": "chunk"}
        return {key: value for key, value in merged.items() if value is not None}

    @classmethod
    def from_store_record(
        cls,
        record_id: str,
        document: str,
        metadata: dict[str, Any] | None,
    ) -> "DocumentChunk":
        payload = dict(metadata or {})
        known_fields = set(cls.model_fields)
        extra_metadata = {
            key: value
            for key, value in payload.items()
            if key not in known_fields and value is not None
        }
        payload["id"] = record_id
        payload["text"] = document
        payload["metadata"] = {**extra_metadata, **payload.get("metadata", {})}
        return cls.model_validate(payload)


class HypotheticalQuestion(BaseModel):
    """A HyPE synthetic question linked to a parent article chunk."""

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    id: str = Field(min_length=1)
    parent_chunk_id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    language: str = Field(min_length=2, max_length=5)
    text: str = Field(min_length=1)
    question_index: int = Field(ge=0)
    article_number: str | None = None
    article_title: str | None = None
    page_start: int = Field(ge=1)
    page_end: int = Field(ge=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_pages(self) -> "HypotheticalQuestion":
        if self.page_end < self.page_start:
            raise ValueError("page_end must be greater than or equal to page_start")
        return self

    def to_metadata(self) -> dict[str, Any]:
        base = self.model_dump(exclude={"text", "metadata"})
        merged = {**base, **self.metadata, "record_type": "hype_question"}
        return {key: value for key, value in merged.items() if value is not None}

    @classmethod
    def from_chunk(
        cls,
        chunk: DocumentChunk,
        question_index: int,
        question: str,
    ) -> "HypotheticalQuestion":
        return cls(
            id=f"{chunk.id}__hype_{question_index}",
            parent_chunk_id=chunk.id,
            source=chunk.source,
            language=chunk.language,
            text=question,
            question_index=question_index,
            article_number=chunk.article_number,
            article_title=chunk.article_title,
            page_start=chunk.page_start,
            page_end=chunk.page_end,
        )
