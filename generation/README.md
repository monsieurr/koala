# Generation Layer

The generation layer turns retrieved legal chunks into grounded answers.

## Included

- `llm.py`
  - runtime LLM settings
  - LiteLLM wrapper
  - Ollama and API-provider support
- `prompt.py`
  - citation-aware prompt construction
  - explicit handling for articles versus recitals
- `chain.py`
  - retrieval-to-answer orchestration
  - extractive fallback when model generation is unavailable

## Design choices

- The LLM is instructed to answer only from supplied context.
- Citations are passed in as numbered context blocks and expected back inline.
- If generation fails, the chain still returns retrieved provisions and excerpts.
