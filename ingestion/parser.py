"""
PDF parser for EU legal documents.

Bug fixes vs V1:
1. Adoption marker search normalises whitespace — handles PyMuPDF line breaks
   inside phrases like "HAVE\nADOPTED\nTHIS REGULATION".
2. split_preamble_and_body also normalises line text before matching.
3. Article pattern handles: trailing spaces, CRLF, missing title line, and
   the rare PyMuPDF artifact where "Article" and the number are on separate lines.
4. Annex pattern anchored to line-start to avoid matching inline references
   like "see Annex I" inside article body text.
5. Added _diagnose() helper that prints what the parser sees — useful when a
   document fails to parse.
"""

import re
import logging
from pathlib import Path
from typing import Optional

import pymupdf as fitz  # PyMuPDF — 'fitz' alias kept for backward compat within this file

from ingestion.languages import LanguageConfig, _normalise, detect_language, get_config
from ingestion.models import DocumentChunk, Language

logger = logging.getLogger(__name__)


# ── Text extraction ────────────────────────────────────────────────────────


def extract_text_with_pages(pdf_path: Path) -> list[tuple[int, str]]:
    """Extract text per page. Returns [(page_number, text), ...] 1-indexed."""
    try:
        doc = fitz.open(str(pdf_path))
    except Exception as e:
        raise RuntimeError(f"Cannot open PDF '{pdf_path}': {e}") from e

    pages = []
    for i, page in enumerate(doc, start=1):
        pages.append((i, page.get_text("text")))
    doc.close()
    return pages


def pages_to_full_text(pages: list[tuple[int, str]]) -> str:
    return "\n".join(text for _, text in pages)


# ── Structure splitting ────────────────────────────────────────────────────


def split_preamble_and_body(
    pages: list[tuple[int, str]], config: LanguageConfig
) -> tuple[list[tuple[int, str]], list[tuple[int, str]]]:
    """
    Split pages into preamble (recitals) and operative body (articles + annexes).

    The adoption marker divides the two. We normalise whitespace on each page's
    text before matching to handle PyMuPDF line-break artifacts.
    """
    split_page = None
    for page_num, text in pages:
        normalised_page = _normalise(text).upper()
        for marker in config.adoption_markers:
            if marker.upper() in normalised_page:
                split_page = page_num
                break
        if split_page is not None:
            break

    if split_page is None:
        logger.warning(
            "Adoption marker not found in any page — treating entire document as body. "
            "Recitals will not be parsed. Run with --diagnose to inspect extracted text."
        )
        return [], pages

    preamble = [(n, t) for n, t in pages if n <= split_page]
    body = [(n, t) for n, t in pages if n > split_page]
    logger.info(f"Preamble: pages 1–{split_page}, body: pages {split_page+1}–{pages[-1][0]}")
    return preamble, body


# ── Recital parsing ────────────────────────────────────────────────────────


# Matches "(47) text..." pattern at start of a logical line
_RECITAL_PATTERN = re.compile(
    r"(?:^|\n)\s*\((\d{1,3})\)\s+(.+?)(?=\n\s*\(\d{1,3}\)\s|\Z)",
    re.DOTALL,
)


def parse_recitals(
    preamble_pages: list[tuple[int, str]],
    source: str,
    language: Language,
) -> list[DocumentChunk]:
    if not preamble_pages:
        return []

    combined = ""
    page_map: list[tuple[int, int]] = []
    for page_num, text in preamble_pages:
        page_map.append((len(combined), page_num))
        combined += text + "\n"

    def offset_to_page(offset: int) -> int:
        page = preamble_pages[0][0]
        for start, pnum in page_map:
            if offset >= start:
                page = pnum
        return page

    # Use a dict keyed by recital number to deduplicate: keep the longest text,
    # which is most likely the genuine recital body rather than an inline reference.
    best: dict[str, DocumentChunk] = {}
    total_matches = 0
    for match in _RECITAL_PATTERN.finditer(combined):
        number = match.group(1)
        text = match.group(2).strip()
        if len(text) < 20:
            continue
        total_matches += 1
        page = offset_to_page(match.start())
        chunk = DocumentChunk(
            id=f"{source}_{language}_recital_{number}",
            source=source,
            language=language,
            chunk_type="recital",
            recital_number=number,
            text=f"({number}) {text}",
            page_start=page,
            page_end=page,
        )
        existing = best.get(number)
        if existing is None or len(text) > len(existing.text):
            best[number] = chunk

    chunks = list(best.values())
    dupes = total_matches - len(chunks)
    if dupes:
        logger.warning(f"Deduplicated {dupes} recital match(es) with repeated numbers (kept longest text per number)")

    logger.info(f"Parsed {len(chunks)} recitals")
    return chunks


# ── Article parsing ────────────────────────────────────────────────────────


def _build_article_pattern(config: LanguageConfig) -> re.Pattern:
    """
    Match article headers robustly.

    Handles:
    - Normal:             "Article 6\nTitle\n"
    - Trailing space:     "Article 6 \nTitle\n"
    - CRLF line endings:  "Article 6\r\nTitle\r\n"
    - No title line:      "Article 6\n1. ..."    (title captured as empty)
    - Blank line between: "Article 6\n\nTitle\n" (rare but seen in some PDFs)

    The title capture group is deliberately liberal ([^\n\r]{0,150}) so it
    tolerates missing titles without failing the match.
    """
    kw = "|".join(re.escape(k) for k in config.article_keywords)
    return re.compile(
        rf"(?m)^(?:{kw})\s+(\d+[a-z]?)\s*\r?\n\s*([^\n\r]{{0,150}})",
    )


def _build_chapter_pattern(config: LanguageConfig) -> re.Pattern:
    kw = "|".join(re.escape(k) for k in config.chapter_keywords)
    return re.compile(
        rf"(?m)^(?:{kw})\s+((?:[IVXLCDM]{{1,8}}|\d+))\s*\r?\n\s*([^\n\r]{{0,150}})",
    )


def _build_annex_pattern(config: LanguageConfig) -> re.Pattern:
    """
    Match annex headings anchored at start-of-line.

    Bug fix vs V1: the old pattern used (?:^|\\n) which also matched inline
    references like "see ANNEX I" inside article body text. Anchoring to
    line-start with a trailing line-end check prevents false positives.
    """
    kw = "|".join(re.escape(k) for k in config.annex_keywords)
    return re.compile(
        rf"(?m)^\s*(?:{kw})\s+([IVXLCDM]{{1,8}}|\d+|[A-Z])\s*(?:\r?\n|$)",
    )


def parse_articles(
    body_pages: list[tuple[int, str]],
    source: str,
    language: Language,
    config: LanguageConfig,
) -> list[DocumentChunk]:
    if not body_pages:
        return []

    combined = ""
    page_map: list[tuple[int, int]] = []
    for page_num, text in body_pages:
        page_map.append((len(combined), page_num))
        combined += text + "\n"

    def offset_to_page(offset: int) -> int:
        page = body_pages[0][0]
        for start, pnum in page_map:
            if offset >= start:
                page = pnum
        return page

    article_pat = _build_article_pattern(config)
    chapter_pat = _build_chapter_pattern(config)
    annex_pat   = _build_annex_pattern(config)

    article_matches = list(article_pat.finditer(combined))
    chapter_matches = list(chapter_pat.finditer(combined))
    annex_match     = annex_pat.search(combined)
    annex_start     = annex_match.start() if annex_match else len(combined)

    if not article_matches:
        logger.warning("No articles found. Run --diagnose to inspect extracted text.")
        return []

    def current_chapter(pos: int) -> tuple[Optional[str], Optional[str]]:
        ch_num, ch_title = None, None
        for m in chapter_matches:
            if m.start() <= pos:
                ch_num   = m.group(1)
                ch_title = m.group(2).strip()
        return ch_num, ch_title

    chunks = []
    for i, match in enumerate(article_matches):
        art_start = match.start()
        art_num   = match.group(1)
        art_title = match.group(2).strip().rstrip("`'\"").strip() if match.group(2) else ""

        next_start = (
            article_matches[i + 1].start()
            if i + 1 < len(article_matches)
            else annex_start
        )

        art_text = combined[art_start:next_start].strip()
        if len(art_text) < 10:
            continue

        ch_num, ch_title = current_chapter(art_start)

        chunks.append(DocumentChunk(
            id=f"{source}_{language}_article_{art_num}",
            source=source,
            language=language,
            chunk_type="article",
            chapter=ch_num,
            chapter_title=ch_title,
            article_number=art_num,
            article_title=art_title or None,
            text=art_text,
            page_start=offset_to_page(art_start),
            page_end=offset_to_page(max(art_start, next_start - 1)),
        ))

    logger.info(f"Parsed {len(chunks)} articles")
    return chunks


# ── Annex parsing ──────────────────────────────────────────────────────────


def parse_annexes(
    body_pages: list[tuple[int, str]],
    source: str,
    language: Language,
    config: LanguageConfig,
) -> list[DocumentChunk]:
    if not body_pages:
        return []

    combined = ""
    page_map: list[tuple[int, int]] = []
    for page_num, text in body_pages:
        page_map.append((len(combined), page_num))
        combined += text + "\n"

    def offset_to_page(offset: int) -> int:
        page = body_pages[0][0]
        for start, pnum in page_map:
            if offset >= start:
                page = pnum
        return page

    annex_pat = _build_annex_pattern(config)
    annex_matches = list(annex_pat.finditer(combined))

    chunks = []
    for i, match in enumerate(annex_matches):
        annex_num = match.group(1)
        start = match.start()
        end   = annex_matches[i + 1].start() if i + 1 < len(annex_matches) else len(combined)
        text  = combined[start:end].strip()

        if len(text) < 10:
            continue

        chunks.append(DocumentChunk(
            id=f"{source}_{language}_annex_{annex_num}",
            source=source,
            language=language,
            chunk_type="annex",
            annex_number=annex_num,
            text=text,
            page_start=offset_to_page(start),
            page_end=offset_to_page(max(start, end - 1)),
        ))

    logger.info(f"Parsed {len(chunks)} annexes")
    return chunks


# ── Diagnostics ────────────────────────────────────────────────────────────


def diagnose(pdf_path: Path, char_sample: int = 300) -> None:
    """
    Print diagnostic information about what the parser sees in a PDF.
    Run via: python -m ingestion.pipeline diagnose --pdf file.pdf
    """
    pages = extract_text_with_pages(pdf_path)
    full  = pages_to_full_text(pages)

    print(f"\nPDF: {pdf_path.name}")
    print(f"Pages: {len(pages)}  |  Total chars: {len(full):,}")
    print()

    # Language detection
    from ingestion.languages import LANGUAGE_CONFIGS, _normalise
    normalised = _normalise(full).upper()

    print("── Adoption marker scan ─────────────────────────")
    found_any = False
    for lang, config in LANGUAGE_CONFIGS.items():
        for marker in config.adoption_markers:
            idx = normalised.find(marker.upper())
            if idx != -1:
                context = full[max(0, idx - 80): idx + len(marker) + 80]
                print(f"  [{lang}] Found at char {idx:,}: ...{repr(context)}...")
                found_any = True
    if not found_any:
        print("  No adoption marker found.")
        # Show chars around 50k and 100k for manual inspection
        for pos in [50_000, 90_000, 120_000]:
            if pos < len(full):
                print(f"\n  Text around char {pos:,}:")
                print(f"  {repr(full[pos:pos+200])}")

    print()
    print("── First 500 chars of extracted text ────────────")
    print(repr(full[:500]))

    print()
    print("── Article header scan (first 5 matches) ────────")
    # Try the English pattern
    pat = re.compile(r"(?m)^Article\s+(\d+[a-z]?)\s*\r?\n\s*([^\n\r]{0,150})")
    matches = list(pat.finditer(full))
    print(f"  Found {len(matches)} article headers")
    for m in matches[:5]:
        print(f"  Art {m.group(1):>4}: {repr(m.group(2)[:80])}")


# ── Public interface ───────────────────────────────────────────────────────


def parse_pdf(
    pdf_path: Path,
    source: str,
    language: Optional[Language] = None,
) -> list[DocumentChunk]:
    """
    Parse a PDF into DocumentChunk objects.

    If language detection fails, run:
        python -m ingestion.pipeline diagnose --pdf <file>
    to inspect what the parser sees.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    logger.info(f"Extracting text from '{pdf_path.name}'…")
    pages    = extract_text_with_pages(pdf_path)
    full_text = pages_to_full_text(pages)

    if language is None:
        language = detect_language(full_text)
        if language is None:
            raise ValueError(
                f"Could not auto-detect language in '{pdf_path.name}'.\n"
                "Options:\n"
                "  1. Pass --language en  (or de/fr/it/es) to override detection.\n"
                "  2. Run: python -m ingestion.pipeline diagnose --pdf <file>\n"
                "     to inspect what the parser extracts from the PDF."
            )
        logger.info(f"Detected language: {language}")
    else:
        logger.info(f"Using specified language: {language}")

    config = get_config(language)
    preamble_pages, body_pages = split_preamble_and_body(pages, config)

    recitals = parse_recitals(preamble_pages, source, language)
    articles = parse_articles(body_pages, source, language, config)
    annexes  = parse_annexes(body_pages, source, language, config)

    all_chunks = recitals + articles + annexes
    logger.info(
        f"Total: {len(recitals)} recitals + {len(articles)} articles "
        f"+ {len(annexes)} annexes = {len(all_chunks)} chunks"
    )

    if len(all_chunks) == 0:
        logger.warning(
            "No chunks produced. Run: python -m ingestion.pipeline diagnose --pdf <file>"
        )
    elif len(articles) < 5:
        logger.warning(
            f"Only {len(articles)} articles found — fewer than expected. "
            "The PDF may have an unusual layout. Run --diagnose to inspect."
        )

    return all_chunks