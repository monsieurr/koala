"""
DocumentChunk model — the core data unit flowing through ingestion and retrieval.
Every chunk maps to exactly one legal structural unit: article, recital, or annex.
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field


ChunkType = Literal["article", "recital", "annex"]
Language = Literal["en", "de", "fr", "it", "es"]


class DocumentChunk(BaseModel):
    # ── Identity ──────────────────────────────────────────────────────────────
    id: str = Field(..., description="Globally unique chunk ID, e.g. 'AI Act_fr_article_13'")
    source: str = Field(..., description="Document name, e.g. 'AI Act'")
    language: Language = Field(..., description="ISO 639-1 language code")

    # ── Structure ─────────────────────────────────────────────────────────────
    chunk_type: ChunkType = Field(..., description="article | recital | annex")
    chapter: Optional[str] = Field(None, description="Chapter number, e.g. 'III'")
    chapter_title: Optional[str] = Field(None, description="Chapter title")

    article_number: Optional[str] = Field(None, description="Article number as string, e.g. '13'")
    article_title: Optional[str] = Field(None, description="Article title if present")
    recital_number: Optional[str] = Field(None, description="Recital number, e.g. '47'")
    annex_number: Optional[str] = Field(None, description="Annex number/label, e.g. 'I' or 'VIII'")

    # ── Content ───────────────────────────────────────────────────────────────
    text: str = Field(..., description="Full verbatim text of the chunk")
    page_start: Optional[int] = Field(None, description="First page in source PDF (1-indexed)")
    page_end: Optional[int] = Field(None, description="Last page in source PDF (1-indexed)")

    # ── Display label (auto-generated) ────────────────────────────────────────
    @property
    def display_label(self) -> str:
        """Human-readable label for UI citation display."""
        if self.chunk_type == "article":
            title = f" — {self.article_title}" if self.article_title else ""
            return f"Article {self.article_number}{title}"
        if self.chunk_type == "recital":
            return f"Recital ({self.recital_number})"
        if self.chunk_type == "annex":
            return f"Annex {self.annex_number}"
        return self.id

    def metadata_dict(self) -> dict:
        """Return all metadata fields (everything except text) as a flat dict.
        Used when storing in ChromaDB, which keeps metadata and documents separate.
        """
        return {
            "id": self.id,
            "source": self.source,
            "language": self.language,
            "chunk_type": self.chunk_type,
            "chapter": self.chapter or "",
            "chapter_title": self.chapter_title or "",
            "article_number": self.article_number or "",
            "article_title": self.article_title or "",
            "recital_number": self.recital_number or "",
            "annex_number": self.annex_number or "",
            "page_start": self.page_start or 0,
            "page_end": self.page_end or 0,
            "display_label": self.display_label,
        }
