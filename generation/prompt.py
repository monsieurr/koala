"""
Prompt builder for the generation layer.

Constructs system and user prompts that:
1. Include retrieved article text verbatim as context
2. Instruct the LLM to cite specific articles by number
3. Distinguish binding obligations (articles) from intent (recitals)
4. Add a CRAG low-confidence caveat when retrieval confidence is low

The prompts are designed to produce grounded, citable compliance answers —
not conversational summaries.
"""

from retrieval.retriever import RetrievalResult

# ── System prompt ──────────────────────────────────────────────────────────

BASE_SYSTEM_PROMPT = """You are an expert in EU regulatory compliance, specialising in the \
EU AI Act and related regulations.

Your role is to answer questions from legal professionals and compliance officers \
with precise, grounded responses that cite the specific legal text.

Rules you must follow:
1. Base your answer ONLY on the provided article excerpts. Do not use general knowledge \
   not present in the context.
2. Always cite the specific article number (e.g. "Article 13", "Article 6(1)") when \
   making a legal claim.
3. Distinguish clearly between:
   - BINDING OBLIGATIONS from articles (use "must", "shall", "is required to")
   - NON-BINDING INTENT from recitals (use "the legislator intends", "according to Recital X")
4. If the context does not contain enough information to answer the question, say so \
   clearly rather than speculating.
5. Structure your answer with a brief direct answer first, then supporting citations.
6. If multiple articles are relevant, cite all of them.
"""

LOW_CONFIDENCE_ADDENDUM = """
⚠️  NOTE: The retrieved context has low confidence for this question. \
The articles shown may not be the most relevant. \
Please review the cited articles directly and consider rephrasing your question if needed.
"""

# ── Prompt builder ────────────────────────────────────────────────────────


def build_system_prompt(low_confidence: bool = False) -> str:
    """Return the system prompt, with an optional low-confidence warning appended."""
    if low_confidence:
        return BASE_SYSTEM_PROMPT + LOW_CONFIDENCE_ADDENDUM
    return BASE_SYSTEM_PROMPT


def build_user_prompt(query: str, retrieval_result: RetrievalResult) -> str:
    """
    Build the user-turn prompt by combining the question with the retrieved context.

    Format:
      QUESTION: <query>

      CONTEXT:
      [Source — Article N — Title]
      <full article text>

      ---

      [Source — Recital (N)]
      <recital text>

      ...

      Please answer the question based only on the context above.
    """
    chunks = retrieval_result.chunks

    if not chunks:
        return (
            f"QUESTION: {query}\n\n"
            "No relevant context was found in the document database. "
            "Please answer based on what you know, clearly noting that no source text "
            "was found."
        )

    # Build context block
    context_parts = []
    for chunk in chunks:
        label = chunk.metadata.get("display_label", chunk.id)
        source = chunk.metadata.get("source", "Unknown source")
        page_start = chunk.metadata.get("page_start")
        page_end = chunk.metadata.get("page_end")
        page_ref = ""
        if page_start and page_end:
            if page_start == page_end:
                page_ref = f" (p. {page_start})"
            else:
                page_ref = f" (pp. {page_start}–{page_end})"

        header = f"[{source} — {label}{page_ref}]"
        context_parts.append(f"{header}\n{chunk.text}")

    context_block = "\n\n---\n\n".join(context_parts)

    return (
        f"QUESTION: {query}\n\n"
        f"CONTEXT:\n\n{context_block}\n\n"
        "---\n\n"
        "Please answer the question based only on the context above. "
        "Cite article numbers explicitly."
    )


def format_citations(retrieval_result: RetrievalResult) -> list[dict]:
    """
    Return a list of citation dicts for display in the UI.

    Each dict has:
      - label       : display label (e.g. "Article 13 — Transparency…")
      - source      : document name
      - language    : language code
      - page_start  : first page
      - page_end    : last page
      - chunk_type  : article | recital | annex
      - rerank_score: cross-encoder confidence score
    """
    citations = []
    for chunk in retrieval_result.chunks:
        meta = chunk.metadata
        citations.append(
            {
                "label": meta.get("display_label", chunk.id),
                "source": meta.get("source", ""),
                "language": meta.get("language", ""),
                "page_start": meta.get("page_start"),
                "page_end": meta.get("page_end"),
                "chunk_type": meta.get("chunk_type", ""),
                "chapter": meta.get("chapter", ""),
                "chapter_title": meta.get("chapter_title", ""),
                "rerank_score": round(chunk.rerank_score, 4),
            }
        )
    return citations
