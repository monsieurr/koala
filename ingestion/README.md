# Layer 1 — Ingestion

Parses EU legal PDFs into structured `DocumentChunk` objects and stores them in ChromaDB.

## Files

| File | Purpose |
|------|---------|
| `models.py` | `DocumentChunk` Pydantic model — the core data unit |
| `languages.py` | Language configs and auto-detection |
| `parser.py` | PDF parsing, structure detection, chunking |
| `store.py` | ChromaDB wrapper: embed, upsert, query, delete |
| `pipeline.py` | CLI orchestrator |

## Chunking strategy

One chunk per legal structural unit:
- **Recitals** — non-binding intent, numbered (1), (2), …
- **Articles** — binding obligations, `Article N`
- **Annexes** — lists and criteria, `ANNEX I`, `ANNEX II`, …

Legal meaning lives at article level. We never split by token count.

## CLI

```bash
python -m ingestion.pipeline ingest --pdf ./data/ai_act.pdf --source "AI Act"
python -m ingestion.pipeline stats
python -m ingestion.pipeline query "transparency obligations"
python -m ingestion.pipeline delete --source "AI Act"
```
