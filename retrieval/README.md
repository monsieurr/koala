# Retrieval Layer

The retrieval layer follows the hybrid pipeline defined in the project specification:

1. BM25 sparse search
2. Dense vector search against stored chunks and optional HyPE questions
3. Reciprocal rank fusion
4. Optional cross-encoder reranking
5. Lightweight confidence scoring
6. Parent expansion to article-level chunks

## HyPE

`retrieval/hype.py` provides an index-time enrichment hook. It accepts any client implementing:

```python
class QuestionGenerator:
    def generate(self, prompt: str) -> str: ...
```

This keeps Layer 2 independent from the future LLM provider abstraction in Layer 3.
