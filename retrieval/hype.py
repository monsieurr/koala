"""HyPE enrichment helpers for index-time hypothetical question generation."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Protocol, Sequence

from ingestion.models import DocumentChunk, HypotheticalQuestion


class QuestionGenerator(Protocol):
    """Minimal protocol for a generation backend that can return free-form text."""

    def generate(self, prompt: str) -> str:
        """Return the model output for the prompt."""


def build_hype_prompt(chunk: DocumentChunk, questions_per_chunk: int) -> str:
    return (
        "You generate search queries for a legal retrieval system.\n"
        f"Produce {questions_per_chunk} distinct natural-language questions that this legal text answers.\n"
        "Keep each question concise, grounded in compliance language, and likely to be asked by a legal or "
        "compliance professional.\n"
        "Return one question per line with no commentary.\n\n"
        f"Source: {chunk.source}\n"
        f"Language: {chunk.language}\n"
        f"Label: {chunk.label()}\n"
        f"Title: {chunk.article_title or 'N/A'}\n"
        f"Text:\n{chunk.text}"
    )


def parse_hype_output(raw_output: str, limit: int) -> list[str]:
    questions: list[str] = []
    for line in raw_output.splitlines():
        cleaned = re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", line).strip()
        if cleaned:
            questions.append(cleaned)

    deduplicated: list[str] = []
    seen: set[str] = set()
    for question in questions:
        lowered = question.casefold()
        if lowered in seen:
            continue
        seen.add(lowered)
        deduplicated.append(question)
        if len(deduplicated) >= limit:
            break
    return deduplicated


@dataclass(slots=True)
class HyPEGenerator:
    """Generate and package hypothetical questions for article chunks."""

    client: QuestionGenerator
    questions_per_chunk: int = 4

    def generate_for_chunks(self, chunks: Sequence[DocumentChunk]) -> list[HypotheticalQuestion]:
        questions: list[HypotheticalQuestion] = []
        for chunk in chunks:
            if chunk.chunk_type != "article":
                continue
            prompt = build_hype_prompt(chunk, self.questions_per_chunk)
            raw_output = self.client.generate(prompt)
            parsed_questions = parse_hype_output(raw_output, self.questions_per_chunk)
            for index, question in enumerate(parsed_questions):
                questions.append(HypotheticalQuestion.from_chunk(chunk, index, question))
        return questions
