"""
Ingestion pipeline CLI.

Commands:
  ingest  — Parse a PDF and store chunks in ChromaDB
  stats   — Show what's currently in the store
  query   — Run a quick test semantic search
  delete  — Remove all chunks for a given source document

Usage:
  python -m ingestion.pipeline ingest --pdf ./data/ai_act.pdf --source "AI Act"
  python -m ingestion.pipeline ingest --pdf ./data/reglement_ia.pdf --source "AI Act" --language fr
  python -m ingestion.pipeline stats
  python -m ingestion.pipeline query "transparency obligations for high-risk AI"
  python -m ingestion.pipeline delete --source "AI Act"
"""

import argparse
import logging
import sys
from pathlib import Path

from ingestion.models import Language
from ingestion.parser import parse_pdf
from ingestion.store import DEFAULT_DB_PATH, DocumentStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Commands ──────────────────────────────────────────────────────────────


def cmd_ingest(args: argparse.Namespace) -> None:
    pdf_path = Path(args.pdf)
    source = args.source
    language: Language | None = args.language

    logger.info(f"=== Ingesting '{pdf_path.name}' as source='{source}' ===")

    # Parse PDF → chunks
    chunks = parse_pdf(pdf_path, source=source, language=language)
    if not chunks:
        logger.error("No chunks produced — check PDF structure and language detection.")
        sys.exit(1)

    # Upsert into ChromaDB
    store = DocumentStore(db_path=DEFAULT_DB_PATH)
    store.upsert_chunks(chunks)

    # Summary
    stats = store.stats()
    print(f"\n✅  Ingestion complete.")
    print(f"   Chunks stored this run : {len(chunks)}")
    print(f"   Total in DB            : {stats['total_chunks']}")


def cmd_stats(args: argparse.Namespace) -> None:
    store = DocumentStore(db_path=DEFAULT_DB_PATH)
    stats = store.stats()

    print(f"\n📊  ChromaDB stats  (path: {DEFAULT_DB_PATH})")
    print(f"   Total entries (incl. HyPE) : {stats['total_chunks']}")
    print(f"   Real document chunks        : {stats['real_chunks']}")

    if not stats["by_source"]:
        print("   No documents ingested yet.")
        return

    print("\n   By source / language:")
    for key, counts in sorted(stats["by_source"].items()):
        print(
            f"     {key:<40}  "
            f"{counts['total']:>4} total  "
            f"({counts['article']} articles, "
            f"{counts['recital']} recitals, "
            f"{counts['annex']} annexes)"
        )


def cmd_query(args: argparse.Namespace) -> None:
    store = DocumentStore(db_path=DEFAULT_DB_PATH)
    question = args.question
    n = args.n

    print(f"\n🔍  Query: \"{question}\"\n")
    results = store.query(question, n_results=n)

    if not results:
        print("  No results found. Have you ingested any documents?")
        return

    for i, r in enumerate(results, 1):
        meta = r["metadata"]
        label = meta.get("display_label", r["id"])
        source = meta.get("source", "?")
        lang = meta.get("language", "?")
        score = 1 - r["distance"]  # cosine distance → similarity
        snippet = r["text"][:200].replace("\n", " ")
        print(f"  {i}. [{source} / {lang}] {label}  (score: {score:.3f})")
        print(f"     {snippet}…\n")


def cmd_delete(args: argparse.Namespace) -> None:
    source = args.source
    store = DocumentStore(db_path=DEFAULT_DB_PATH)
    n = store.delete_by_source(source)
    print(f"\nDeleted {n} chunks for source \'{source}\'.")


def cmd_diagnose(args: argparse.Namespace) -> None:
    """
    Print what the parser extracts from a PDF — no data is stored.
    Run this first when a document fails to ingest.
    """
    from ingestion.parser import diagnose
    diagnose(Path(args.pdf))


# ── CLI wiring ─────────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m ingestion.pipeline",
        description="AI Act Compliance Tool — ingestion pipeline",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # ingest
    p_ingest = sub.add_parser("ingest", help="Parse and store a PDF")
    p_ingest.add_argument("--pdf", required=True, help="Path to the PDF file")
    p_ingest.add_argument("--source", required=True, help='Document name, e.g. "AI Act"')
    p_ingest.add_argument(
        "--language",
        choices=["en", "de", "fr", "it", "es"],
        default=None,
        help="Force language (auto-detected if omitted)",
    )

    # stats
    sub.add_parser("stats", help="Show database statistics")

    # query
    p_query = sub.add_parser("query", help="Run a test semantic search")
    p_query.add_argument("question", help="Natural language question")
    p_query.add_argument("-n", type=int, default=5, help="Number of results (default: 5)")

    # delete
    p_delete = sub.add_parser("delete", help="Delete all chunks for a source")
    p_delete.add_argument("--source", required=True, help="Source name to delete")

    # diagnose
    p_diag = sub.add_parser("diagnose", help="Inspect what the parser sees in a PDF")
    p_diag.add_argument("--pdf", required=True, help="Path to the PDF file")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    dispatch = {
        "ingest": cmd_ingest,
        "stats": cmd_stats,
        "query": cmd_query,
        "delete": cmd_delete,
        "diagnose": cmd_diagnose,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
