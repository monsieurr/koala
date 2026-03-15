"""CLI orchestrator for ingestion and retrieval tasks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from ingestion.parser import LegalDocumentParser
from ingestion.store import ChromaVectorStore
from retrieval.retriever import HybridRetriever


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="EU AI compliance ingestion and retrieval pipeline")
    parser.add_argument(
        "--persist-directory",
        default="data/chroma",
        help="Directory used by ChromaDB for persistence.",
    )
    parser.add_argument(
        "--collection-name",
        default="legal_documents",
        help="ChromaDB collection name.",
    )
    parser.add_argument(
        "--embedding-model",
        default="sentence-transformers/all-MiniLM-L6-v2",
        help="Sentence-transformers embedding model name.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest = subparsers.add_parser("ingest", help="Parse and ingest a legal PDF")
    ingest.add_argument("--pdf", required=True, help="Path to the source PDF")
    ingest.add_argument("--source", required=True, help='Logical source name, e.g. "AI Act"')
    ingest.add_argument("-l", "--language", help="Optional language override: en, de, fr, it, es")

    stats = subparsers.add_parser("stats", help="Show collection statistics")
    stats.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")

    query = subparsers.add_parser("query", help="Run a hybrid retrieval query")
    query.add_argument("question", help="Natural-language compliance question")
    query.add_argument("--source", action="append", dest="sources", help="Filter to one or more sources")
    query.add_argument("--language", action="append", dest="languages", help="Filter to one or more languages")
    query.add_argument("--top-k", type=int, default=5, help="Number of chunks to return")
    query.add_argument(
        "--reranker-model",
        default="cross-encoder/ms-marco-MiniLM-L-6-v2",
        help="Cross-encoder model name used for reranking.",
    )

    delete = subparsers.add_parser("delete", help="Delete all records for a source")
    delete.add_argument("--source", required=True, help='Logical source name, e.g. "AI Act"')

    return parser


def run_ingest(args: argparse.Namespace) -> dict[str, object]:
    parser = LegalDocumentParser()
    store = _build_store(args)
    pdf_path = Path(args.pdf)
    chunks = parser.parse_pdf(pdf_path, source=args.source, language=args.language)
    result = store.ingest(chunks)
    return {
        "status": "ok",
        "pdf": str(pdf_path),
        "source": args.source,
        "language": args.language or chunks[0].language,
        "chunks": result["chunks"],
        "hypothetical_questions": result["hypothetical_questions"],
    }


def run_stats(args: argparse.Namespace) -> dict[str, object]:
    store = _build_store(args)
    return store.stats()


def run_query(args: argparse.Namespace) -> dict[str, object]:
    store = _build_store(args)
    retriever = HybridRetriever(store, reranker_model=args.reranker_model)
    result = retriever.retrieve(
        args.question,
        top_k=args.top_k,
        source_filters=args.sources,
        language_filters=args.languages,
    )
    return result.to_dict()


def run_delete(args: argparse.Namespace) -> dict[str, object]:
    store = _build_store(args)
    store.delete_source(args.source)
    return {"status": "ok", "deleted_source": args.source}


def _build_store(args: argparse.Namespace) -> ChromaVectorStore:
    return ChromaVectorStore(
        persist_directory=args.persist_directory,
        collection_name=args.collection_name,
        embedding_model=args.embedding_model,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "ingest":
        payload = run_ingest(args)
    elif args.command == "stats":
        payload = run_stats(args)
    elif args.command == "query":
        payload = run_query(args)
    elif args.command == "delete":
        payload = run_delete(args)
    else:
        raise ValueError(f"Unsupported command: {args.command}")

    indent = 2 if getattr(args, "pretty", False) else None
    print(json.dumps(payload, indent=indent, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
