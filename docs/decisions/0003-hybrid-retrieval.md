# 3. Hybrid retrieval: BM25 plus embeddings, merged with reciprocal rank fusion

**Status:** accepted

## Context
Legal questions mix exact tokens ("DW-500", "Rev. C", "Exhibit 3", a case number, a defined term) with paraphrase ("when did they find out"). Embeddings handle paraphrase but blur exact identifiers; keyword search is the reverse.

## Decision
Search runs BM25 over the case's chunks and, when an API key is configured, cosine similarity over stored embeddings. Results are merged with reciprocal rank fusion (k = 60), which needs no score calibration between the two. The agent can also filter a search to one exhibit.

## Consequences
- Search still works with no API key (BM25 only), which keeps tests and the CI eval offline and free.
- The offline retrieval eval finds the expected page in the top 6 for all 15 answerable golden questions. CI fails if recall drops below 90%.
- Vectors live in SQLite as float32 blobs and are scored with NumPy per query. That's fine for one case at a time (thousands of chunks). Larger matters need an ANN index (pgvector, Vertex AI Vector Search).
