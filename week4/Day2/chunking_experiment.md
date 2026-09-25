# Chunking Experiment — MiniLM (Day 2)

## Setup
- Corpus: property descriptions + FAQs + developer notes.
- Embedder: `sentence-transformers/all-MiniLM-L6-v2` (384-dim, local).
- Query set: 20 UrduLish real-estate prompts (budget, installment, possession, location intent).
- Metric:
  - **Retrieval@3 quality** = relevant context found in top-3
  - **Avg retrieval latency** per query
  - **Context noise** = non-relevant chunk ratio in top-3

## Results
| Chunk Size (tokens) | Overlap | Retrieval@3 | Avg Latency (ms) | Context Noise |
|---:|---:|---:|---:|---:|
| 256 | 32 | 0.83 | 86 | 0.24 |
| 512 | 64 | 0.90 | 103 | 0.18 |
| 1024 | 128 | 0.88 | 129 | 0.26 |
| 2048 | 256 | 0.80 | 171 | 0.34 |

## Selection
**Chosen chunk size: 512 tokens (64 overlap).**

Reasoning:
- Best Retrieval@3 in test set.
- Latency remains inside Day 3 end-to-end budget envelope.
- Lower noise than larger chunks, preserving grounding reliability.

## Results Table (Decision View)
| Criterion | Winner | Why |
|---|---|---|
| Relevance | 512 | Highest Retrieval@3 |
| Latency | 256 | Fastest, but lower relevance |
| Precision balance | 512 | Best quality-latency tradeoff |

## Verdict
512-token chunks with 64-token overlap provide the best production tradeoff for this UrduLish real-estate RAG corpus.

## What I'd change in v2
- Add BM25+vector hybrid reranking before final top-k.
- Expand UrduLish query set to 100+ prompts with spelling variants.
- Benchmark multilingual embedding alternatives while staying local-first.
