# Ingestion Layer

The ingestion layer turns EU legal PDFs into retrievable chunks and stores them in ChromaDB with local embeddings.

## Chunking strategy

- One chunk per recital
- One chunk per article
- One chunk per annex
- No arbitrary token splitting

## CLI

```bash
python -m ingestion.pipeline ingest --pdf ./data/pdfs/ai_act.pdf --source "AI Act"
python -m ingestion.pipeline ingest --pdf ./data/pdfs/reglement_ia.pdf --source "AI Act" --language fr
python -m ingestion.pipeline stats
python -m ingestion.pipeline query "transparency obligations for high-risk AI"
python -m ingestion.pipeline delete --source "AI Act"
```

## Supported languages

- `en`
- `de`
- `fr`
- `it`
- `es`

Language detection uses adoption marker phrases and can be overridden with `--language`.
