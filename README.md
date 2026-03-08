# EU AI Act Compliance Tool

An open source, self-hostable AI-powered compliance tool for EU legal documents.
Ask natural language questions and receive grounded, cited answers pointing to
specific articles, recitals, and annexes.

Built for legal and compliance professionals. Runs with one command. No cloud required.

---

## What's new in V2

| Bug | Status |
|-----|--------|
| ChromaDB multi-key `where` filter broken (silently wrong results) | ✅ Fixed — uses `$and` |
| `get_chain()` not cached — cross-encoder reloaded every message | ✅ Fixed — `@st.cache_resource` |
| Streaming spinner fired on wrong code (retrieval was outside it) | ✅ Fixed — eager retrieval |
| Citations empty after streaming (lost on discarded chain instance) | ✅ Fixed — direct from retrieval |
| Sidebar called `get_all()` to list sources (fetches all text) | ✅ Fixed — uses `stats()` |
| `get_all()` + `where` + HyPE filter — HyPE not excluded | ✅ Fixed |
| No Docker support | ✅ Added — Dockerfile + docker-compose |
| Thin error handling in store.py and retriever.py | ✅ Added throughout |

---

## Quick Start

### Without Docker

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. (For local models) Start Ollama
ollama serve
ollama pull mistral

# 3. Ingest a document
python -m ingestion.pipeline ingest \
    --pdf ./data/ai_act_en.pdf \
    --source "AI Act"

# 4. Launch
streamlit run app.py
```

Open http://localhost:8501

---

### With Docker

```bash
# First run — build and pull the default Ollama model
docker compose --profile setup up --build

# Subsequent runs
docker compose up

# Ingest a document (from host, while containers are running)
docker compose exec app python -m ingestion.pipeline ingest \
    --pdf /app/data/pdfs/ai_act.pdf \
    --source "AI Act"
```

To use API models instead of Ollama, set keys in `.env`:

```bash
cp .env.example .env
# edit .env with your API keys
docker compose up
```

---

## Model Guidance

| Hardware | Model | Command |
|----------|-------|---------|
| 8 GB RAM | Mistral 7B Q4 | `ollama pull mistral` |
| 16 GB RAM | Llama 3.1 8B | `ollama pull llama3.1` |
| 16 GB RAM | Gemma 2 9B | `ollama pull gemma2:9b` |
| 24 GB+ RAM | Qwen 2.5 14B | `ollama pull qwen2.5:14b` |
| API (good) | GPT-4o-mini | Set `OPENAI_API_KEY` |
| API (best) | Claude Sonnet | Set `ANTHROPIC_API_KEY` |

---

## Architecture

```
Layer 1 — Ingestion     Parse EU PDFs → structured chunks → ChromaDB
Layer 2 — Retrieval     BM25 + Dense + RRF + Cross-encoder + CRAG
Layer 3 — Generation    LiteLLM → Ollama/API → cited answer
Layer 4 — UI            Streamlit chat interface
```

### Retrieval pipeline

```
User question
    ↓
1. BM25 search          → top 20  (exact terms, article numbers)
2. Dense search         → top 20  (semantic similarity)
3. RRF fusion           → merged top 20
4. Cross-encoder rerank → top 5
5. CRAG confidence      → score + low-confidence warning
6. Context passed to LLM
```

---

## CLI Reference

```bash
python -m ingestion.pipeline ingest --pdf <path> --source <name> [--language <code>]
python -m ingestion.pipeline stats
python -m ingestion.pipeline query "transparency obligations for high-risk AI"
python -m ingestion.pipeline delete --source "AI Act"
```

---

## Supported Languages

| Code | Language |
|------|----------|
| `en` | English |
| `de` | Deutsch |
| `fr` | Français |
| `it` | Italiano |
| `es` | Español |

---

## Project Structure

```
ai-act-compliance/
├── ingestion/          Layer 1 — PDF parsing + ChromaDB storage
├── retrieval/          Layer 2 — Hybrid search + reranking
├── generation/         Layer 3 — LLM + prompting + chain
├── app.py              Layer 4 — Streamlit UI
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

---

## Licence

MIT


An open source, self-hostable AI-powered compliance tool for EU legal documents.
Ask natural language questions and receive grounded, cited answers pointing to
specific articles, recitals, and annexes.

Built for legal and compliance professionals. Runs with one command. No cloud required.

---

## Features

- **Grounded answers** — every claim is backed by a specific article citation
- **Hybrid retrieval** — BM25 + dense search + RRF + cross-encoder reranking
- **HyPE** — hypothetical question embeddings for better retrieval accuracy
- **Multi-language** — EN, DE, FR, IT, ES document versions
- **Local-first** — run entirely offline with Ollama (no API key needed)
- **API support** — OpenAI, Anthropic, Mistral, or any OpenAI-compatible endpoint
- **CRAG confidence** — warns you when retrieval confidence is low

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. (Optional) Set up Ollama for local models

```bash
# Install Ollama from https://ollama.ai, then:
ollama serve
ollama pull mistral        # 8 GB RAM
# ollama pull llama3.1     # 16 GB RAM
# ollama pull qwen2.5:14b  # 24 GB+ RAM
```

### 3. Ingest a document

```bash
python -m ingestion.pipeline ingest \
    --pdf ./data/ai_act_en.pdf \
    --source "AI Act"

# French version:
python -m ingestion.pipeline ingest \
    --pdf ./data/reglement_ia.pdf \
    --source "AI Act" \
    --language fr
```

### 4. Launch the UI

```bash
streamlit run app.py
```

Open http://localhost:8501 in your browser.

---

## Architecture

```
Layer 1 — Ingestion     Parse EU PDFs → structured chunks → ChromaDB
Layer 2 — Retrieval     BM25 + Dense + RRF + Cross-encoder + CRAG
Layer 3 — Generation    LiteLLM → Ollama/API → cited answer
Layer 4 — UI            Streamlit chat interface
```

### Retrieval pipeline

```
User question
    ↓
1. BM25 search          → top 20  (exact terms, article numbers)
2. Dense search         → top 20  (semantic similarity)
3. RRF fusion           → merged top 20
4. Cross-encoder rerank → top 5
5. CRAG confidence      → score + low-confidence warning
6. Context passed to LLM
```

### Chunking strategy

One chunk per legal structural unit — article, recital, or annex.
Never splits at arbitrary token counts; legal meaning lives at article level.

---

## CLI Reference

```bash
# Ingest a PDF
python -m ingestion.pipeline ingest --pdf <path> --source <name> [--language <code>]

# Check what's stored
python -m ingestion.pipeline stats

# Test retrieval
python -m ingestion.pipeline query "transparency obligations for high-risk AI"

# Delete a source
python -m ingestion.pipeline delete --source "AI Act"
```

---

## Model Guidance

| Hardware | Model | Command |
|----------|-------|---------|
| 8 GB RAM | Mistral 7B Q4 | `ollama pull mistral` |
| 16 GB RAM | Llama 3.1 8B | `ollama pull llama3.1` |
| 16 GB RAM | Gemma 2 9B | `ollama pull gemma2:9b` |
| 24 GB+ RAM | Qwen 2.5 14B | `ollama pull qwen2.5:14b` |
| API (good) | GPT-4o-mini | Set `OPENAI_API_KEY` |
| API (best) | Claude Sonnet | Set `ANTHROPIC_API_KEY` |

---

## Supported Languages

| Code | Language | Notes |
|------|----------|-------|
| `en` | English | Primary legal lingua franca |
| `de` | Deutsch | |
| `fr` | Français | |
| `it` | Italiano | |
| `es` | Español | |

Language is auto-detected from the adoption marker phrase in the preamble.
Use `--language <code>` to override if detection fails.

---

## HyPE Enrichment (optional)

HyPE generates hypothetical questions for each article at index time,
improving retrieval accuracy with no runtime cost.

```python
from ingestion.store import DocumentStore
from generation.llm import LLMClient, LLMConfig, make_llm_callable
from retrieval.hype import enrich_store_with_hype

store = DocumentStore()
llm = LLMClient(LLMConfig(model="ollama/mistral"))
enrich_store_with_hype(store, make_llm_callable(llm), source="AI Act")
```

---

## Project Structure

```
ai-act-compliance/
├── ingestion/
│   ├── models.py       DocumentChunk Pydantic model
│   ├── languages.py    Language configs + auto-detection
│   ├── parser.py       PDF parsing, structure detection, chunking
│   ├── store.py        ChromaDB wrapper, embedding, persistence
│   └── pipeline.py     CLI orchestrator
├── retrieval/
│   ├── bm25.py         Sparse BM25 index
│   ├── retriever.py    Hybrid search + RRF + reranker + CRAG
│   └── hype.py         HyPE: hypothetical question generation
├── generation/
│   ├── llm.py          LiteLLM wrapper
│   ├── prompt.py       Prompt builder with citations
│   └── chain.py        End-to-end orchestration
├── app.py              Streamlit UI (single file)
├── data/
│   ├── chroma/         ChromaDB persistence (gitignored)
│   └── pdfs/           Source PDFs (gitignored)
├── requirements.txt
├── .env.example
└── README.md
```

---

## Contributing

This is an open source project. Contributions welcome.

Areas of interest:
- Additional EU documents (GDPR, NIS2, Data Act)
- More languages (PL, RO, NL, PT, EL)
- Feedback loop for answer quality improvement
- Docker packaging for easy deployment

---

## Licence

MIT
