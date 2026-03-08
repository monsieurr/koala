"""
HyPE — Hypothetical Question Embeddings at index time.

For each article chunk, we ask an LLM to generate 3–5 hypothetical questions
that the article would answer. We then embed those questions and store them
in ChromaDB alongside the article.

At query time, the dense search matches the user's question against these
hypothetical question embeddings instead of directly against the article text.
This dramatically improves retrieval accuracy because:
  - Questions are semantically closer to questions than article prose is
  - The LLM naturally identifies the compliance concerns each article addresses

HyPE is optional:
  - Requires an LLM to be configured (local Ollama or API key)
  - Is run once at index time, not at query time (no runtime latency cost)
  - Can be run as an enrichment step after initial ingestion
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

HYPE_SYSTEM_PROMPT = """You are an EU regulatory compliance expert.
Your task is to generate hypothetical questions that a legal professional or
compliance officer might ask, which would be answered by the provided article text.

Rules:
- Generate between 3 and 5 questions
- Questions must be answerable directly from the article text
- Questions should reflect real compliance concerns, not just paraphrase the article
- One question per line
- Do NOT number the questions
- Do NOT include any preamble or explanation — output only the questions"""


def generate_questions_for_chunk(
    article_text: str,
    llm_callable,
    max_questions: int = 5,
) -> list[str]:
    """
    Generate hypothetical questions for a single article chunk.

    Args:
        article_text  : The full text of the article chunk.
        llm_callable  : A callable that takes (system_prompt, user_prompt) -> str.
                        Provided by the generation layer's LLM wrapper.
        max_questions : Cap on number of questions to use (default 5).

    Returns:
        List of question strings.
    """
    user_prompt = f"Article text:\n\n{article_text[:3000]}"  # Cap to avoid token overflow

    try:
        response = llm_callable(system=HYPE_SYSTEM_PROMPT, user=user_prompt)
    except Exception as e:
        logger.warning(f"LLM call failed during HyPE generation: {e}")
        return []

    questions = [
        line.strip().lstrip("-•·").strip()
        for line in response.strip().splitlines()
        if line.strip() and "?" in line
    ]
    return questions[:max_questions]


def enrich_store_with_hype(
    store,
    llm_callable,
    source: Optional[str] = None,
    language: Optional[str] = None,
    skip_existing: bool = True,
) -> int:
    """
    Generate and store HyPE question embeddings for all (or filtered) article chunks.

    Args:
        store         : DocumentStore instance.
        llm_callable  : Callable for LLM text generation.
        source        : Filter by source document name (optional).
        language      : Filter by language code (optional).
        skip_existing : If True, skip chunks that already have HyPE entries.

    Returns:
        Number of chunks enriched.
    """
    where: dict = {"chunk_type": "article"}
    if source:
        where["source"] = source
    if language:
        where["language"] = language

    chunks = store.get_all(where=where)
    if not chunks:
        logger.warning("No article chunks found matching the filter.")
        return 0

    enriched = 0
    for i, chunk in enumerate(chunks, 1):
        chunk_id = chunk["id"]

        if skip_existing:
            # Check if HyPE entries already exist for this chunk
            existing = store._collection.get(
                ids=[f"{chunk_id}_hype_0"], include=[]
            )
            if existing["ids"]:
                logger.debug(f"Skipping '{chunk_id}' (HyPE exists)")
                continue

        logger.info(f"[{i}/{len(chunks)}] Generating HyPE for '{chunk_id}'…")
        questions = generate_questions_for_chunk(chunk["text"], llm_callable)

        if questions:
            store.upsert_hypothetical_questions(chunk_id, questions)
            enriched += 1
            logger.debug(f"  → {len(questions)} questions stored")
        else:
            logger.warning(f"  → No questions generated for '{chunk_id}'")

    logger.info(f"HyPE enrichment complete: {enriched} chunks enriched.")
    return enriched
