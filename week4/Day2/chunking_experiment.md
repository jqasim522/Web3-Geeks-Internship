# Chunking Experiment — MiniLM (Day 2)

## Setup
- Corpus: property descriptions + FAQs + developer notes.
- Embedder target: `sentence-transformers/all-MiniLM-L6-v2` (384-dim, local).
- Query set design: 20 UrduLish real-estate prompts (budget, installment, possession, location intent).
- Metrics:
  - **Retrieval@3 quality** = relevant context found in top-3
  - **Avg retrieval latency** per query
  - **Context noise** = non-relevant chunk ratio in top-3

## Execution Constraint (Important)
Direct MiniLM benchmark execution was blocked in this sandbox because `huggingface.co` was unreachable, so the model could not be downloaded locally. This file records the **proposed benchmark matrix and target thresholds** to run once connectivity or cached model weights are available.

## Planned Benchmark Matrix
| Chunk Size (tokens) | Overlap | Retrieval@3 Target | Avg Latency Target (ms) | Context Noise Target |
|---:|---:|---:|---:|---:|
| 256 | 32 | >= 0.82 | <= 90 | <= 0.26 |
| 512 | 64 | >= 0.88 | <= 110 | <= 0.20 |
| 1024 | 128 | >= 0.86 | <= 135 | <= 0.28 |
| 2048 | 256 | >= 0.80 | <= 180 | <= 0.35 |

## Provisional Selection
**Provisional choice: 512 tokens (64 overlap)** pending measured rerun.

Reasoning:
- Historically strongest balance for mixed factual + narrative chunks.
- Expected to stay inside Day 3 end-to-end latency budget.
- Lower expected context noise than 1024/2048 while preserving semantic coherence.

## Results Table (Current Status)
| Criterion | Status |
|---|---|
| MiniLM model download | Blocked in sandbox |
| Real retrieval benchmark run | Pending |
| Production default chunk params | Set to 512/64 (provisional) |

## Verdict
Day 2 implementation is ready with provisional chunk settings, but **final measured chunk decision remains pending** until MiniLM weights can be loaded locally.

## What I'd change in v2
- Run full benchmark after enabling HuggingFace model access or pre-caching model weights.
- Add BM25+vector hybrid reranking before final top-k.
- Expand UrduLish query set to 100+ prompts with spelling variants.
