# Koala — AI Governance Assistant

Open-source, self-hostable AI governance assistant for teams that build AI. Ask grounded questions about the EU AI Act,
track your AI portfolio, and compare the AI Act with the Digital Omnibus on AI proposal.

Current implementation status:

- Layer 1: ingestion and ChromaDB persistence
- Layer 2: hybrid retrieval with BM25, dense search, RRF fusion, reranking, and HyPE hooks
- Layer 3: grounded answer generation with a LiteLLM wrapper and extractive fallback
- Layer 4: FastAPI backend with query, ingest, health, source, and config endpoints
- Layer 5: SvelteKit frontend with chat, model controls, citations, and source filters
- Layer 5.1: Regime-aware source presets (AI Act vs Digital Omnibus on AI proposal)
- Layer 6: Dockerfiles, compose stack, and env-driven configuration

## What is included

- PDF parsing into recital, article, and annex chunks
- Language detection for `en`, `de`, `fr`, `it`, and `es`
- Local embeddings via `sentence-transformers`
- Persistent vector storage via ChromaDB
- Sparse BM25 index built from stored chunks
- Hybrid retriever with:
  - BM25 top-k
  - dense top-k
  - reciprocal rank fusion
  - optional cross-encoder reranking
  - lightweight confidence scoring
  - HyPE hypothetical-question enrichment support
- Grounded answer generation with:
  - LiteLLM-based provider abstraction
  - Ollama, OpenAI, Anthropic, Mistral, and OpenAI-compatible settings
  - citation-aware prompt construction
  - extractive fallback when model generation is unavailable
- FastAPI API with:
  - `POST /query`
  - `POST /ingest`
  - `GET /sources`
  - `GET /health`
  - `GET /config`
  - `DELETE /sources/{id}`
- SvelteKit frontend with:
  - chat interface
  - provider/model selector
  - source and language filters
  - regime toggle for AI Act vs Digital Omnibus on AI proposal
  - confidence and citation display
- Containerized deployment with separate backend and frontend images

## Quickstart

Recommended Python version: 3.12 (see `.python-version`).

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run the backend locally:

```bash
uvicorn api.main:app --reload
```

Run the frontend locally:

```bash
cd frontend
npm install
npm run dev
```

Ingest the AI Act through the CLI:

```bash
python -m ingestion.pipeline ingest --pdf ./data/pdfs/OJ_L_202401689_EN_TXT.pdf --source "AI Act (EU 2024/1689)"
```

Ingest the Digital Omnibus on AI proposal:

```bash
python -m ingestion.pipeline ingest --pdf ./data/pdfs/CELEX_52025PC0836_EN_TXT.pdf --source "Digital Omnibus on AI (COM(2025) 836)"
```

Or ingest through the API:

```bash
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{"pdf_path":"./data/pdfs/ai_act.pdf","source":"AI Act (EU 2024/1689)"}'
```

```bash
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{"pdf_path":"./data/pdfs/CELEX_52025PC0836_EN_TXT.pdf","source":"Digital Omnibus on AI (COM(2025) 836)"}'
```

Note: the Regime toggle auto-selects sources by name. Keep source labels recognizable (e.g., “AI Act (EU 2024/1689)” and
“Digital Omnibus on AI (COM(2025) 836)”) so the presets can find them.

Query the API:

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question":"What are the transparency obligations for high-risk AI systems?"}'
```

Run the full stack with Docker:

```bash
cp .env.example .env
docker compose up --build
```

## Demo mode (serverless-friendly)

The public demo runs in **demo mode**:

- Catalog entries are stored in the browser only (cleared when site data is removed).
- Local assistants (Ollama) are disabled; hosted providers require your API key.
- Retrieval runs in **lightweight mode (BM25 only)** to keep the serverless bundle size small.

To enable demo mode in a deployment, set:

```bash
PUBLIC_DEMO_MODE=1
```

For the **full local deployment** with semantic retrieval and reranking, install the full dependency set:

```bash
pip install .[full]
```

Or keep using the existing full dependency file:

```bash
pip install -r requirements.txt
```

## Project layout

```text
ingestion/           PDF parsing, language detection, chunk models, ChromaDB wrapper, CLI
retrieval/           BM25 index, hybrid retriever, HyPE helpers
generation/          LiteLLM wrapper, prompts, retrieval-to-answer chain
api/                 FastAPI app, settings, schemas, routes
frontend/            SvelteKit chat client
data/                ChromaDB persistence and local PDFs
Dockerfile.backend   Python API image
Dockerfile.frontend  SvelteKit image
docker-compose.yml   Two-service local deployment
```

## Notes

- The parser is intentionally simple and article-oriented to preserve legal meaning.
- Dense retrieval and reranking degrade gracefully when optional model dependencies are unavailable.
- Answer generation degrades to an extractive fallback when LiteLLM is not installed or no provider is reachable.
- Local backend runs default to `http://localhost:11434`.
- Docker overrides Ollama to `http://host.docker.internal:11434` via compose.
