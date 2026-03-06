# RAG Configuration Guide — TB-Scale Document Intelligence

> **Retrieval-Augmented Generation at enterprise scale** — Multi-vector retrieval, cross-encoder reranking, Gemini 1.5 Pro 1M-token synthesis.

---

## Overview

The Alti RAG Engine is purpose-built for **heavy commercial data**:
- Annual reports (500+ page PDFs)
- Clinical trial databases (millions of records)
- Legal contract portfolios (10GB+)
- Financial filings (SEC, Basel III, regulatory reports)
- Technical manuals, EHR exports, support ticket archives

**Performance baseline** (production, `us-central1`):
| Metric | Value |
|---|---|
| Corpus capacity | Unlimited (BigQuery-backed) |
| Documents ingested | 10M+ per tenant |
| Chunks in vector index | 1B+ per tenant |
| Retrieval latency (top-50 RRF) | < 200ms |
| End-to-end RAG latency (with rerank) | < 1,000ms |
| NDCG@10 vs mono-vector | +23% |

---

## Table of Contents
1. [Document Ingestion](#document-ingestion)
2. [Chunking Strategies](#chunking-strategies)
3. [Multi-Vector Retrieval](#multi-vector-retrieval)
4. [Reranking](#reranking)
5. [Query Decomposition](#query-decomposition)
6. [Long-Context Synthesis](#long-context-synthesis)
7. [Performance Tuning](#performance-tuning)
8. [Monitoring & Quality](#monitoring--quality)

---

## Document Ingestion

### Supported Formats

| Format | Extraction | Chunking | Notes |
|---|---|---|---|
| PDF | Document AI OCR + layout | SECTION | Tables preserved as TABLE_UNIT chunks |
| DOCX | Structure-aware parser | PARAGRAPH | Headings preserved for section metadata |
| XLSX | Schema-aware table parser | TABLE_UNIT | Each sheet = separate document context |
| HTML | BeautifulSoup + boilerplate removal | PARAGRAPH | HTML stripped, markdown preserved |
| JSON | jq-based field extraction | SECTION | Nested objects flattened to context |
| CSV | Row batching | TABLE_UNIT | 500-row batches with schema header repeated |
| EMAIL | MIME parser | SENTENCE | Threads reassembled |
| XML | XPath extraction | SECTION | Namespace-aware |

### Ingestion Pipeline

```
Cloud Storage (gs://tenant-docs/...)
    │ Cloud Storage trigger
    ▼
Document AI (OCR + layout detection)
    │ Structured document output
    ▼
Chunker Service (hierarchical, per-type strategy)
    │ List of DocumentChunk objects
    ▼
Vertex AI Embeddings API (text-embedding-004)
    │ 768-dim vectors (batched at 250 docs/request)
    ▼
BigQuery streaming insert (alti_rag.document_chunks)
    │
Vertex AI Vector Search upsert (ANN index)
```

**Ingestion throughput**: ~500 pages/minute (per Cloud Tasks worker). Scale by increasing Cloud Tasks workers.

### API Usage

```python
# Single document
doc = await client.rag.ingest(
    source_uri="gs://my-bucket/annual-report-2025.pdf",
    doc_type="PDF",
    title="Annual Report 2025",
    department="finance",
    classification="CONFIDENTIAL",  # PUBLIC|INTERNAL|CONFIDENTIAL|SECRET
    language="en-US",
    metadata={"fiscal_year": "2025", "author": "CFO Office"}
)

# Bulk ingestion (folder)
docs = await client.rag.ingest_folder(
    source_prefix="gs://my-bucket/contracts/",
    doc_type="DOCX",
    department="legal",
    classification="CONFIDENTIAL"
)
print(f"Queued {len(docs)} documents for ingestion")
```

---

## Chunking Strategies

### Strategy Selection (Automatic)

| Document Type | Auto-Selected Strategy | Target Tokens | Overlap |
|---|---|---|---|
| PDF (≤ 100 pages) | SECTION | 512 tokens | 10% |
| PDF (> 100 pages) | TOPIC_SEG | 1,024 tokens | 5% |
| DOCX | PARAGRAPH | 384 tokens | 10% |
| XLSX / CSV | TABLE_UNIT | 768 tokens | 0% (tables are atomic) |
| HTML | PARAGRAPH | 448 tokens | 5% |
| EMAIL | SENTENCE | 256 tokens | 0% |
| JSON | SECTION | 384 tokens | 0% |

### Manual Override

```python
from alti_sdk.rag import ChunkStrategy

doc = await client.rag.ingest(
    source_uri="gs://my-bucket/large-contract.pdf",
    doc_type="PDF",
    chunk_strategy=ChunkStrategy.SENTENCE,  # Override: granular for Q&A
    chunk_target_tokens=256,
    chunk_overlap_pct=0.15,
    title="Master Service Agreement 2025"
)
```

### Why TABLE_UNIT Matters

Spreadsheets and tables are **never split** in the middle. A financial table like:

```
Q1 Revenue | Q2 Revenue | Q3 Revenue | Q4 Revenue
  $1.2M    |   $1.8M   |   $2.1M   |   $2.4M
```

Split across two chunks would make Q1-Q2 in one chunk and Q3-Q4 in another. Both chunks would lose context. TABLE_UNIT keeps the entire table together, ensuring complete retrieval.

---

## Multi-Vector Retrieval

### Dense Retrieval (Semantic)

Uses **Vertex AI text-embedding-004** (768-dimensional, multilingual):

- Captures semantic similarity: "quarterly revenue" ≈ "Q3 income" ≈ "trimestrale entrate"
- Indexed in Vertex AI Vector Search (ScaNN ANN algorithm)
- Query time: ~40ms at 1B vectors

### Sparse Retrieval (Keyword)

Uses **BM25** (Best Match 25):

```
BM25 score = Σ IDF(t) × tf(t,d) × (k1+1) / (tf(t,d) + k1 × (1 - b + b × dl/avgdl))
where k1=1.5, b=0.75
```

- Excels at exact terms: "Basel III CET1", "HCAHPS composite", regulation clause numbers
- Run in BigQuery via `SEARCH` function on tokenized text
- Query time: ~50ms

### Reciprocal Rank Fusion (RRF)

Combines dense and sparse ranked lists without requiring score normalization:

```python
rrf_score(chunk) = 1/(K + rank_dense) + 1/(K + rank_sparse)
# K=60 prevents high scores for very low ranked items
```

**Why RRF works**: Dense and sparse signals are complementary — dense finds semantically similar documents even when exact terms differ; sparse ensures high-precision retrieval for specific technical terminology.

### Metadata Filtering

Applied before or alongside retrieval to scope the search:

```python
response = await client.rag.query(
    "What are our Q3 2025 liquidity ratios?",
    filters={
        "department":        "finance",           # AND filter
        "classification":    "CONFIDENTIAL",
        "doc_date_after":    "2025-07-01",        # After Q3 start
        "doc_date_before":   "2025-10-01",        # Before Q4
        "language":          "en-US",
        "source_uri_prefix": "gs://my-bucket/regulatory/",
    }
)
```

---

## Reranking

### Why Rerank?

Bi-encoder retrieval (dense + sparse) is fast but imprecise — models embed query and passage independently, missing fine-grained relevance signals. A **cross-encoder reranker** reads query + passage together, capturing precise relevance.

**Impact**: +15% NDCG@10 at the cost of ~200ms extra latency.

### Cross-Encoder Reranker

The reranker scores the top-50 RRF candidates by joint query-passage relevance:

```
Input: (query, passage_text) → concatenated
Output: relevance_score ∈ [0, 1]
```

Trained on enterprise QA pairs from legal, financial, clinical, and technical domains.

### Configuring Reranking

```python
# Default: rerank=True, top_k=50, top_n=12
response = await client.rag.query(
    query="What are the contraindications for Drug X in patients with renal failure?",
    top_k=100,       # Retrieve more candidates for reranker
    top_n=15,        # Return top-15 after reranking (more for complex synthesis)
    rerank=True,
)

# High-precision mode (slower but most accurate)
response = await client.rag.query(
    query=query,
    top_k=200,
    top_n=20,
    rerank=True,
    retrieval_mode="FULL",   # dense + sparse + metadata
)
```

---

## Query Decomposition

For **complex multi-hop questions**, the engine decomposes into parallel sub-queries:

### When Decomposition Triggers

| Pattern | Example | Sub-queries |
|---|---|---|
| Multi-jurisdiction | "EU, US, and APAC CET1 ratios" | 1 per jurisdiction + benchmark |
| Multi-period | "Q3 vs Q4 vs full year" | 1 per period |
| Multi-entity | "across all product tiers" | 1 per entity |
| Causal chain | "What caused X and what is the result Y" | X query + Y query |

### Example

```
Complex query:
"What was our Basel III CET1 ratio across all EU, US, and APAC
 jurisdictions in Q3 2025 and how does it compare to industry peers?"

Decomposed into:
  [1] "Basel III CET1 ratio Q3 2025 EU jurisdiction"
  [2] "Basel III CET1 ratio Q3 2025 US jurisdiction"
  [3] "Basel III CET1 ratio Q3 2025 APAC jurisdiction"
  [4] "Industry average CET1 ratio Q3 2025 banking sector benchmarks"

Each sub-query → parallel retrieval → individual answers
→ Synthesis model merges 4 answers into cohesive response with citations
```

---

## Long-Context Synthesis

### Gemini 1.5 Pro: 1M Token Context Window

When total retrieved context < 800,000 tokens (approx. 2,400 pages), the engine **stuffs the entire retrieved corpus** into Gemini 1.5 Pro's context window. This is called **long-context mode**.

Benefits:
- No information loss from truncation
- Model can reason across distant document sections
- Higher accuracy than RAG-then-generate for complex questions

When to use:
- Legal: "Find every clause across 500 contracts that references change-of-control conditions"
- Clinical: "Across all patient records from 2025, summarize the most common adverse drug reaction patterns"
- Financial: "Synthesize all material disclosures from SEC filings that mention refinancing risk"

```python
response = await client.rag.query(
    query="Summarize all change-of-control clauses across our contract portfolio",
    top_k=500,           # Retrieve many chunks
    use_long_context=True,  # Enable 1M-token mode
    top_n=100,           # Keep top-100 after rerank
)
print(f"Model: {response.model_used}")       # gemini-1.5-pro
print(f"Context: {response.context_tokens:,} tokens")
```

---

## Performance Tuning

### Retrieval Latency

| Configuration | Latency | Quality |
|---|---|---|
| `mode=DENSE, top_k=10, rerank=False` | ~80ms | Moderate |
| `mode=HYBRID, top_k=50, rerank=False` | ~150ms | Good |
| `mode=FULL, top_k=50, rerank=True, top_n=12` | ~400ms | Excellent |
| `mode=FULL, top_k=200, rerank=True, top_n=20` | ~700ms | Best |

### Index Temperature

Vertex AI Vector Search allows configuring index freshness vs. recall:

```python
# Real-time index (high recall, slightly slower)
# Best for: < 10M documents, frequently updated
index_config = {
    "algorithm": "SCANN",
    "distance_measure": "COSINE",
    "leaf_nodes": 500,
    "leaf_search_percent": 10,  # Search 10% of leaves
}

# Batch index (lower recall, faster)
# Best for: > 100M documents, infrequently updated
index_config["leaf_search_percent"] = 3
```

---

## Monitoring & Quality

### Key Metrics to Monitor

| Metric | Threshold | Action if Breached |
|---|---|---|
| Retrieval NDCG@10 | ≥ 0.75 | Re-evaluate chunking strategy |
| Average confidence | ≥ 0.80 | Review retrieval top_k / reranker |
| Embedding latency p99 | ≤ 200ms | Scale Vertex AI embedding endpoint |
| RAG end-to-end p99 | ≤ 1,000ms | Reduce top_k or disable rerank |
| Document ingestion lag | ≤ 10 min | Scale Cloud Tasks workers |
| Corpus drift (dead chunks) | ≤ 5% | Run corpus maintenance job weekly |

### Quality Evaluation

```bash
# Run NDCG evaluation on labelled QA pairs (monthly)
python services/rag-engine/evaluate.py \
  --eval-set gs://alti-evals/rag-qa-pairs-legal.jsonl \
  --tenant-id t-bank \
  --mode FULL \
  --output gs://alti-evals/results/$(date +%Y%m%d).json
```

### Corpus Maintenance

```bash
# Remove stale chunks (documents deleted from source but chunks remain)
python services/rag-engine/maintenance.py \
  --tenant-id t-bank \
  --action prune-orphans

# Re-embed with newer model version (run after model upgrade)
python services/rag-engine/maintenance.py \
  --tenant-id t-bank \
  --action re-embed \
  --model text-embedding-005  # when available
```
