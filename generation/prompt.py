"""Prompt builder for grounded compliance answers."""

from __future__ import annotations

from typing import Sequence

from retrieval.retriever import RetrievalHit


def build_citation_label(hit: RetrievalHit, index: int) -> str:
    title = hit.chunk.article_title or hit.chunk.metadata.get("section_title")
    if title:
        return f"[{index}] {hit.chunk.label()} - {title}"
    return f"[{index}] {hit.chunk.label()}"


def build_context_block(hit: RetrievalHit, index: int) -> str:
    chunk = hit.chunk
    title = chunk.article_title or chunk.metadata.get("section_title") or "Untitled section"
    authority = "binding obligation" if chunk.chunk_type in {"article", "annex"} else "recital / interpretive context"
    return (
        f"{build_citation_label(hit, index)}\n"
        f"Source: {chunk.source} ({chunk.language})\n"
        f"Type: {chunk.chunk_type} ({authority})\n"
        f"Pages: {chunk.page_start}-{chunk.page_end}\n"
        f"Title: {title}\n"
        f"Text:\n{chunk.text}"
    )


def build_messages(
    question: str,
    hits: Sequence[RetrievalHit],
    *,
    low_confidence: bool,
    user_role: str | None = None,
    system_context: dict[str, object] | None = None,
) -> list[dict[str, str]]:
    context_blocks = [build_context_block(hit, index) for index, hit in enumerate(hits, start=1)]
    confidence_note = (
        "Retrieval confidence is low. State that the answer may be incomplete and advise verification."
        if low_confidence
        else "Retrieval confidence is acceptable."
    )
    request_context: list[str] = []
    if user_role:
        request_context.append(
            f"Questioner's role under the AI Act: {user_role}. Tailor the answer to that role where relevant."
        )
    if system_context:
        system_lines = ["AI system context:"]
        for label, key in (
            ("Name", "name"),
            ("Description", "description"),
            ("Type", "system_type"),
            ("Stored risk level", "level_of_risk"),
            ("Stored confidence", "confidence"),
        ):
            value = system_context.get(key)
            if value is not None and str(value).strip():
                system_lines.append(f"{label}: {value}")
        request_context.append("\n".join(system_lines))
    system_prompt = (
        "You are a careful EU legal compliance assistant.\n"
        "Answer only from the supplied legal context.\n"
        "Distinguish binding obligations in articles and annexes from explanatory recitals.\n"
        "Do not invent obligations, thresholds, deadlines, or exceptions.\n"
        "If the context is insufficient, say so explicitly.\n"
        "Cite sources inline using the provided square-bracket references like [1] or [2].\n"
        "Answer in the same language as the user's question when possible."
    )
    user_prompt = (
        f"Question:\n{question}\n\n"
        + (f"Request context:\n{chr(10).join(request_context)}\n\n" if request_context else "")
        + f"Instruction:\n{confidence_note}\n"
        + "Give a concise answer first, then add a short 'Legal basis' paragraph.\n\n"
        + "Context:\n"
        + "\n\n".join(context_blocks)
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
