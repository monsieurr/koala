"""End-to-end retrieval to answer generation orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
import re
from typing import Any, Sequence

from generation.llm import LLMDependencyError, LLMSettings, LiteLLMClient
from generation.prompt import build_citation_label, build_messages
from retrieval.retriever import HybridRetriever, RetrievalHit


@dataclass(slots=True)
class Citation:
    index: int
    id: str
    label: str
    source: str
    language: str
    chunk_type: str
    title: str | None
    article_number: str | None
    recital_number: str | None
    annex_number: str | None
    page_start: int
    page_end: int
    excerpt: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "id": self.id,
            "label": self.label,
            "source": self.source,
            "language": self.language,
            "chunk_type": self.chunk_type,
            "title": self.title,
            "article_number": self.article_number,
            "recital_number": self.recital_number,
            "annex_number": self.annex_number,
            "page_start": self.page_start,
            "page_end": self.page_end,
            "excerpt": self.excerpt,
        }


@dataclass(slots=True)
class AnswerResult:
    question: str
    answer: str
    citations: list[Citation]
    confidence: float
    low_confidence: bool
    warning: str | None
    answer_mode: str
    retrieval_debug: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "answer": self.answer,
            "citations": [citation.to_dict() for citation in self.citations],
            "confidence": self.confidence,
            "low_confidence": self.low_confidence,
            "warning": self.warning,
            "answer_mode": self.answer_mode,
            "retrieval_debug": self.retrieval_debug,
        }


class ComplianceAnswerChain:
    """Retrieve relevant provisions and synthesize a grounded answer."""

    def __init__(
        self,
        retriever: HybridRetriever,
        *,
        default_llm_settings: LLMSettings | None = None,
    ) -> None:
        self.retriever = retriever
        self.default_llm_settings = default_llm_settings or LLMSettings.from_env()

    def answer(
        self,
        question: str,
        *,
        source_filters: Sequence[str] | None = None,
        language_filters: Sequence[str] | None = None,
        top_k: int = 5,
        user_role: str | None = None,
        system_context: dict[str, object] | None = None,
        llm_settings: LLMSettings | None = None,
    ) -> AnswerResult:
        retrieval = self.retriever.retrieve(
            question,
            top_k=top_k,
            source_filters=source_filters,
            language_filters=language_filters,
        )
        citations = self._build_citations(retrieval.hits)
        if not retrieval.hits:
            return AnswerResult(
                question=question,
                answer=(
                    "I could not find relevant provisions in the indexed documents for this question. "
                    "Try narrowing the scope, adding a source filter, or ingesting the relevant document first."
                ),
                citations=[],
                confidence=0.0,
                low_confidence=True,
                warning="No supporting legal context was retrieved.",
                answer_mode="not_found",
                retrieval_debug=retrieval.debug,
            )

        active_settings = llm_settings or self.default_llm_settings
        try:
            answer = self._generate_answer(
                question,
                retrieval.hits,
                retrieval.low_confidence,
                active_settings,
                user_role=user_role,
                system_context=system_context,
            )
            mode = "generated"
        except LLMDependencyError:
            logging.getLogger("koala.chain").info(
                "llm_fallback",
                extra={"event": "answer.fallback", "reason": "llm_unavailable"},
            )
            answer = self._fallback_answer(question, retrieval.hits, citations, retrieval.low_confidence)
            mode = "sources_only"

        return AnswerResult(
            question=question,
            answer=answer,
            citations=citations,
            confidence=retrieval.confidence,
            low_confidence=retrieval.low_confidence,
            warning=retrieval.warning,
            answer_mode=mode,
            retrieval_debug=retrieval.debug,
        )

    def _generate_answer(
        self,
        question: str,
        hits: Sequence[RetrievalHit],
        low_confidence: bool,
        settings: LLMSettings,
        *,
        user_role: str | None = None,
        system_context: dict[str, object] | None = None,
    ) -> str:
        client = LiteLLMClient(settings)
        messages = build_messages(
            question,
            hits,
            low_confidence=low_confidence,
            user_role=user_role,
            system_context=system_context,
        )
        return client.complete(messages)

    def _build_citations(self, hits: Sequence[RetrievalHit]) -> list[Citation]:
        citations: list[Citation] = []
        for index, hit in enumerate(hits, start=1):
            chunk = hit.chunk
            title = chunk.article_title or chunk.metadata.get("section_title")
            excerpt = chunk.text[:360].strip()
            citations.append(
                Citation(
                    index=index,
                    id=chunk.id,
                    label=build_citation_label(hit, index),
                    source=chunk.source,
                    language=chunk.language,
                    chunk_type=chunk.chunk_type,
                    title=title,
                    article_number=chunk.article_number,
                    recital_number=chunk.recital_number,
                    annex_number=chunk.annex_number,
                    page_start=chunk.page_start,
                    page_end=chunk.page_end,
                    excerpt=excerpt,
                )
            )
        return citations

    def _fallback_answer(
        self,
        question: str,
        hits: Sequence[RetrievalHit],
        citations: Sequence[Citation],
        low_confidence: bool,
    ) -> str:
        summary_lines = [
            "Sources-only response (model generation is unavailable).",
            f"Question: {question}",
            "Relevant provisions:",
        ]

        for hit, citation in list(zip(hits, citations))[:4]:
            excerpt = _select_key_sentence(hit.chunk.text) or citation.excerpt
            title = f" — {citation.title}" if citation.title else ""
            summary_lines.append(f"{citation.label}{title}: {excerpt}")

        if low_confidence:
            summary_lines.append(
                "Retrieval confidence is low, so verify the cited provisions directly."
            )
        summary_lines.append("Next step: review the cited provisions to confirm the exact obligations.")
        return "\n\n".join(summary_lines)


def _select_key_sentence(text: str) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    keywords = ("shall", "must", "required", "oblig", "prohibit", "shall not", "must not")
    for sentence in sentences:
        candidate = sentence.strip()
        if not candidate:
            continue
        lowered = candidate.lower()
        if any(keyword in lowered for keyword in keywords):
            return _truncate_sentence(candidate)
    return _truncate_sentence(sentences[0]) if sentences else ""


def _truncate_sentence(sentence: str, limit: int = 220) -> str:
    cleaned = sentence.strip()
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[:limit].rsplit(' ', 1)[0]}…"
