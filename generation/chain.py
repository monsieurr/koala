"""
Generation chain — end-to-end retrieval → generation orchestration.

The chain is the single entry point used by the Streamlit UI.
It wires the retriever and LLM client together and returns both
the generated answer and the source citations.
"""

import logging
from dataclasses import dataclass, field
from typing import Iterator, Optional

from generation.llm import LLMClient, LLMConfig
from generation.prompt import build_system_prompt, build_user_prompt, format_citations
from ingestion.store import DEFAULT_DB_PATH, DocumentStore
from retrieval.retriever import Retriever, RetrievalResult

logger = logging.getLogger(__name__)


# ── Chain output ──────────────────────────────────────────────────────────


@dataclass
class ChainResult:
    """The full output of a chain.run() or chain.stream() call."""
    answer: str = ""
    citations: list[dict] = field(default_factory=list)
    low_confidence: bool = False
    confidence_score: float = 1.0
    query: str = ""
    retrieval: Optional[RetrievalResult] = None


# ── Chain ─────────────────────────────────────────────────────────────────


class ComplianceChain:
    """
    Orchestrates retrieval + generation for a compliance question.

    Usage:
        chain = ComplianceChain(llm_config=LLMConfig(model="ollama/mistral"))

        # Blocking
        result = chain.run("What are the transparency obligations for high-risk AI?")
        print(result.answer)
        for cite in result.citations:
            print(cite["label"])

        # Streaming (for UI)
        for token in chain.stream("What is a high-risk AI system?"):
            print(token, end="", flush=True)
    """

    def __init__(
        self,
        llm_config: Optional[LLMConfig] = None,
        store: Optional[DocumentStore] = None,
        retriever: Optional[Retriever] = None,
        source_filter: Optional[str] = None,
        language_filter: Optional[str] = None,
    ):
        """
        Args:
            llm_config       : LLMConfig; defaults to local Ollama/mistral.
            store            : Shared DocumentStore; created if None.
            retriever        : Shared Retriever; created if None.
            source_filter    : Restrict retrieval to this source document.
            language_filter  : Restrict retrieval to this language.
        """
        self.llm_config = llm_config or LLMConfig()
        self.llm = LLMClient(self.llm_config)
        self.store = store or DocumentStore(db_path=DEFAULT_DB_PATH)
        self.retriever = retriever or Retriever(store=self.store)
        self.source_filter = source_filter
        self.language_filter = language_filter

    def run(self, query: str) -> ChainResult:
        """
        Blocking retrieval + generation.

        Args:
            query: Natural language compliance question.

        Returns:
            ChainResult with answer text, citations, and confidence metadata.
        """
        retrieval = self._retrieve(query)
        system = build_system_prompt(low_confidence=retrieval.low_confidence)
        user = build_user_prompt(query, retrieval)

        try:
            answer = self.llm.complete(system=system, user=user)
        except RuntimeError as e:
            logger.error(f"LLM generation failed: {e}")
            return ChainResult(
                answer=str(e),
                citations=format_citations(retrieval),
                low_confidence=True,
                confidence_score=0.0,
                query=query,
                retrieval=retrieval,
            )

        return ChainResult(
            answer=answer,
            citations=format_citations(retrieval),
            low_confidence=retrieval.low_confidence,
            confidence_score=retrieval.confidence_score,
            query=query,
            retrieval=retrieval,
        )

    def stream(self, query: str) -> Iterator[str]:
        """
        Streaming generation — yields string tokens as the LLM produces them.
        Used by the Streamlit UI for a responsive chat experience.

        Yields token strings. The caller is responsible for assembling and displaying them.
        Note: citations are NOT available during streaming; call get_last_citations() after.
        """
        retrieval = self._retrieve(query)
        self._last_retrieval = retrieval  # Store for post-stream citation access

        system = build_system_prompt(low_confidence=retrieval.low_confidence)
        user = build_user_prompt(query, retrieval)

        yield from self.llm.stream(system=system, user=user)

    def get_last_citations(self) -> list[dict]:
        """
        Return citations from the most recent stream() call.
        Call this after consuming the full stream iterator.
        """
        if hasattr(self, "_last_retrieval"):
            return format_citations(self._last_retrieval)
        return []

    def get_last_confidence(self) -> tuple[bool, float]:
        """
        Return (low_confidence, confidence_score) from the most recent stream() call.
        """
        if hasattr(self, "_last_retrieval"):
            return self._last_retrieval.low_confidence, self._last_retrieval.confidence_score
        return False, 1.0

    def rebuild_index(self) -> None:
        """Rebuild the BM25 index — call after ingesting new documents."""
        self.retriever._rebuild_bm25()

    # ── Internal ───────────────────────────────────────────────────────────

    def _retrieve(self, query: str) -> RetrievalResult:
        return self.retriever.retrieve(
            query=query,
            source=self.source_filter,
            language=self.language_filter,
        )
