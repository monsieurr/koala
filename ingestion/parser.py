"""PDF parser that extracts recital, article, and annex chunks."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from pathlib import Path
from typing import Iterable

from .languages import LanguageConfig, detect_language, get_language_config, normalize_for_matching
from .models import DocumentChunk, slugify_fragment


class ParserDependencyError(RuntimeError):
    """Raised when the optional PDF parser dependency is missing."""


@dataclass(slots=True)
class TaggedLine:
    text: str
    page: int


@dataclass(slots=True)
class SectionBuffer:
    kind: str
    number: str
    title: str | None
    chapter: str | None
    chapter_title: str | None
    lines: list[TaggedLine] = field(default_factory=list)

    @property
    def page_start(self) -> int:
        return self.lines[0].page

    @property
    def page_end(self) -> int:
        return self.lines[-1].page


class LegalDocumentParser:
    """Best-effort parser for EU legal PDFs."""

    _RECITAL_PATTERN = re.compile(r"^\((\d+)\)\s*(.*)$")
    _ROMAN_PATTERN = r"[IVXLCDM]+"
    _ARTICLE_NUMBER_PATTERN = r"[0-9]+[A-Za-z]?"
    _PUNCTUATION_START = tuple(",;:.)]")

    def parse_pdf(self, pdf_path: str | Path, source: str, language: str | None = None) -> list[DocumentChunk]:
        lines = self._extract_lines(pdf_path)
        if not lines:
            raise ValueError(f"No text could be extracted from {pdf_path}")

        joined_text = "\n".join(line.text for line in lines)
        detected_language = language.lower() if language else detect_language(joined_text)
        config = get_language_config(detected_language)
        adoption_index = self._find_adoption_marker(lines, config)
        recital_start_index = self._find_recital_start(lines, config, stop_index=adoption_index)

        recital_slice_start = recital_start_index + 1 if recital_start_index >= 0 else 0
        recital_lines = (
            lines[recital_slice_start:adoption_index]
            if adoption_index >= 0
            else lines[recital_slice_start:]
        )
        body_lines = lines[adoption_index + 1 :] if adoption_index >= 0 else []

        chunks: list[DocumentChunk] = []
        chunks.extend(self._parse_recitals(recital_lines, source, detected_language))
        chunks.extend(self._parse_body(body_lines, source, detected_language, config))
        chunks = self._deduplicate_chunks(chunks)

        if not chunks:
            raise ValueError(
                "The parser did not detect any recital, article, or annex sections. "
                "The PDF may require a source-specific parser adjustment."
            )
        return chunks

    def _extract_lines(self, pdf_path: str | Path) -> list[TaggedLine]:
        try:
            import fitz
        except ImportError as exc:
            raise ParserDependencyError(
                "PyMuPDF is required for PDF parsing. Install dependencies from requirements.txt."
            ) from exc

        lines: list[TaggedLine] = []
        with fitz.open(str(pdf_path)) as document:
            for page_index, page in enumerate(document, start=1):
                text = page.get_text("text")
                for raw_line in text.splitlines():
                    line = " ".join(raw_line.split())
                    if line:
                        lines.append(TaggedLine(text=line, page=page_index))
        return lines

    def _find_adoption_marker(self, lines: Iterable[TaggedLine], config: LanguageConfig) -> int:
        normalized_markers = {normalize_for_matching(marker) for marker in config.adoption_markers}
        for index, line in enumerate(lines):
            normalized = normalize_for_matching(line.text)
            if any(marker in normalized for marker in normalized_markers):
                return index
        return -1

    def _find_recital_start(
        self,
        lines: list[TaggedLine],
        config: LanguageConfig,
        *,
        stop_index: int,
    ) -> int:
        normalized_markers = {normalize_for_matching(marker) for marker in config.recital_start_markers}
        if not normalized_markers:
            return -1
        limit = stop_index if stop_index >= 0 else len(lines)
        for index, line in enumerate(lines[:limit]):
            normalized = normalize_for_matching(line.text)
            if any(marker == normalized for marker in normalized_markers):
                return index
        return -1

    def _parse_recitals(self, lines: list[TaggedLine], source: str, language: str) -> list[DocumentChunk]:
        chunks: list[DocumentChunk] = []
        current_number: str | None = None
        current_lines: list[TaggedLine] = []
        highest_number = 0

        def flush() -> None:
            nonlocal current_number, current_lines
            if not current_number or not current_lines:
                current_number = None
                current_lines = []
                return
            text = "\n".join(line.text for line in current_lines).strip()
            chunks.append(
                DocumentChunk(
                    id=f"{slugify_fragment(source)}_{language}_recital_{slugify_fragment(current_number)}",
                    source=source,
                    language=language,
                    chunk_type="recital",
                    text=text,
                    recital_number=current_number,
                    page_start=current_lines[0].page,
                    page_end=current_lines[-1].page,
                )
            )
            current_number = None
            current_lines = []

        for line in lines:
            match = self._RECITAL_PATTERN.match(line.text)
            if match:
                recital_number = int(match.group(1))
                if recital_number <= highest_number:
                    continue
                flush()
                current_number = match.group(1)
                highest_number = recital_number
                remainder = match.group(2).strip()
                current_lines = [TaggedLine(text=remainder or f"({current_number})", page=line.page)]
                continue
            if current_lines:
                current_lines.append(line)

        flush()
        return chunks

    def _parse_body(
        self,
        lines: list[TaggedLine],
        source: str,
        language: str,
        config: LanguageConfig,
    ) -> list[DocumentChunk]:
        if not lines:
            return []

        article_pattern = re.compile(
            rf"^{re.escape(config.article_word)}\s+({self._ARTICLE_NUMBER_PATTERN})\s*(.*)$",
            re.IGNORECASE,
        )
        annex_pattern = re.compile(
            rf"^{re.escape(config.annex_word)}\s+([0-9A-Za-z-]+|{self._ROMAN_PATTERN})\s*(.*)$",
            re.IGNORECASE,
        )
        chapter_pattern = re.compile(
            rf"^{re.escape(config.chapter_word)}\s+({self._ROMAN_PATTERN}|[0-9A-Za-z-]+)\s*(.*)$",
            re.IGNORECASE,
        )

        chunks: list[DocumentChunk] = []
        current_section: SectionBuffer | None = None
        current_chapter: str | None = None
        current_chapter_title: str | None = None
        index = 0

        def flush() -> None:
            nonlocal current_section
            if current_section is None or not current_section.lines:
                current_section = None
                return
            text = "\n".join(line.text for line in current_section.lines).strip()
            chunk_id_number = slugify_fragment(current_section.number)
            if current_section.kind == "article":
                chunks.append(
                    DocumentChunk(
                        id=f"{slugify_fragment(source)}_{language}_article_{chunk_id_number}",
                        source=source,
                        language=language,
                        chunk_type="article",
                        text=text,
                        chapter=current_section.chapter,
                        chapter_title=current_section.chapter_title,
                        article_number=current_section.number,
                        article_title=current_section.title,
                        page_start=current_section.page_start,
                        page_end=current_section.page_end,
                    )
                )
            else:
                chunks.append(
                    DocumentChunk(
                        id=f"{slugify_fragment(source)}_{language}_annex_{chunk_id_number}",
                        source=source,
                        language=language,
                        chunk_type="annex",
                        text=text,
                        annex_number=current_section.number,
                        page_start=current_section.page_start,
                        page_end=current_section.page_end,
                        metadata={"section_title": current_section.title} if current_section.title else {},
                    )
                )
            current_section = None

        while index < len(lines):
            line = lines[index]
            text = line.text.strip()
            if not text:
                index += 1
                continue

            chapter_match = chapter_pattern.match(text)
            if chapter_match:
                current_chapter = chapter_match.group(1)
                inline_title = chapter_match.group(2).strip() or None
                current_chapter_title, consumed_index = self._resolve_inline_or_next_title(
                    lines,
                    index,
                    inline_title,
                    article_pattern,
                    annex_pattern,
                    chapter_pattern,
                )
                index = consumed_index + 1
                continue

            article_match = article_pattern.match(text)
            if article_match and self._is_probable_heading(
                lines=lines,
                start_index=index,
                inline_title=article_match.group(2).strip() or None,
                article_pattern=article_pattern,
                annex_pattern=annex_pattern,
                chapter_pattern=chapter_pattern,
            ):
                flush()
                current_section, index = self._start_section(
                    lines=lines,
                    start_index=index,
                    kind="article",
                    number=article_match.group(1),
                    inline_title=article_match.group(2).strip() or None,
                    chapter=current_chapter,
                    chapter_title=current_chapter_title,
                    article_pattern=article_pattern,
                    annex_pattern=annex_pattern,
                    chapter_pattern=chapter_pattern,
                )
                index += 1
                continue

            annex_match = annex_pattern.match(text)
            if annex_match and self._is_probable_heading(
                lines=lines,
                start_index=index,
                inline_title=annex_match.group(2).strip() or None,
                article_pattern=article_pattern,
                annex_pattern=annex_pattern,
                chapter_pattern=chapter_pattern,
            ):
                flush()
                current_section, index = self._start_section(
                    lines=lines,
                    start_index=index,
                    kind="annex",
                    number=annex_match.group(1),
                    inline_title=annex_match.group(2).strip() or None,
                    chapter=None,
                    chapter_title=None,
                    article_pattern=article_pattern,
                    annex_pattern=annex_pattern,
                    chapter_pattern=chapter_pattern,
                )
                index += 1
                continue

            if current_section is not None:
                current_section.lines.append(line)
            index += 1

        flush()
        return chunks

    def _is_probable_heading(
        self,
        *,
        lines: list[TaggedLine],
        start_index: int,
        inline_title: str | None,
        article_pattern: re.Pattern[str],
        annex_pattern: re.Pattern[str],
        chapter_pattern: re.Pattern[str],
    ) -> bool:
        if inline_title:
            return self._is_probable_heading_text(inline_title)

        title, _ = self._resolve_inline_or_next_title(
            lines,
            start_index,
            inline_title,
            article_pattern,
            annex_pattern,
            chapter_pattern,
        )
        return title is not None and self._is_probable_heading_text(title)

    def _is_probable_heading_text(self, text: str) -> bool:
        stripped = text.strip()
        if not stripped:
            return False
        if stripped.startswith(self._PUNCTUATION_START):
            return False
        return not stripped[0].islower()

    def _start_section(
        self,
        *,
        lines: list[TaggedLine],
        start_index: int,
        kind: str,
        number: str,
        inline_title: str | None,
        chapter: str | None,
        chapter_title: str | None,
        article_pattern: re.Pattern[str],
        annex_pattern: re.Pattern[str],
        chapter_pattern: re.Pattern[str],
    ) -> tuple[SectionBuffer, int]:
        section_lines = [lines[start_index]]
        title, consumed_index = self._resolve_inline_or_next_title(
            lines,
            start_index,
            inline_title,
            article_pattern,
            annex_pattern,
            chapter_pattern,
        )
        if consumed_index > start_index:
            section_lines.extend(lines[start_index + 1 : consumed_index + 1])

        section = SectionBuffer(
            kind=kind,
            number=number,
            title=title,
            chapter=chapter,
            chapter_title=chapter_title,
            lines=section_lines,
        )
        return section, consumed_index

    def _resolve_inline_or_next_title(
        self,
        lines: list[TaggedLine],
        start_index: int,
        inline_title: str | None,
        article_pattern: re.Pattern[str],
        annex_pattern: re.Pattern[str],
        chapter_pattern: re.Pattern[str],
    ) -> tuple[str | None, int]:
        if inline_title:
            return inline_title, start_index

        lookahead = start_index + 1
        while lookahead < len(lines):
            candidate = lines[lookahead].text.strip()
            if not candidate:
                lookahead += 1
                continue
            if (
                article_pattern.match(candidate)
                or annex_pattern.match(candidate)
                or chapter_pattern.match(candidate)
                or self._RECITAL_PATTERN.match(candidate)
            ):
                return None, start_index
            return candidate, lookahead
        return None, start_index

    def _deduplicate_chunks(self, chunks: list[DocumentChunk]) -> list[DocumentChunk]:
        if not chunks:
            return []

        best_by_id: dict[str, DocumentChunk] = {}
        order: list[str] = []
        for chunk in chunks:
            existing = best_by_id.get(chunk.id)
            if existing is None:
                best_by_id[chunk.id] = chunk
                order.append(chunk.id)
                continue

            if self._chunk_priority(chunk) > self._chunk_priority(existing):
                best_by_id[chunk.id] = chunk

        return [best_by_id[chunk_id] for chunk_id in order]

    def _chunk_priority(self, chunk: DocumentChunk) -> tuple[int, int, int]:
        return (
            len(chunk.text),
            chunk.page_end - chunk.page_start,
            -chunk.page_start,
        )
