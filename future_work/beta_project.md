# Project Brief — Option β: Multimodal Personal Memory & Retrieval System

**Status:** future work · not active
**Drafted:** 2026-05-16
**Predecessor concept:** the original `clipThat.py` placeholder, taken seriously

---

## One-line statement

A multimodal capture/recall system that ingests screenshots, voice memos, web pages, and clipboard content, indexes them with a domain-tuned retriever, and answers cited natural-language queries with latency and faithfulness measured against a reproducible benchmark.

---

## Why this is a defensible flagship

It hits all five AI Systems flagship criteria from the Tadashi CV (Segment 2):

| Criterion | How β satisfies it |
|---|---|
| Train + eval + deploy pipeline | Fine-tune retriever/reranker, eval suite, deployed inference + capture clients |
| Real dataset | Your own multimodal corpus + synthetic query/document pairs |
| Reproducible experiments | Versioned scenarios, fixed seeds, tracked checkpoints |
| Tracked metrics | nDCG@10, MRR, hit@k, answer faithfulness, latency P50/P99, cost/query |
| Inference API or edge deployment | FastAPI service + browser extension or menu-bar capture client |
| Clear research question | "Does domain-adapted retrieval beat zero-shot embedding search on personal multimodal data?" |

Retrieval engineering is a well-defined subfield with established benchmarks (BEIR, MTEB) — every design choice is defensible under interview drilling.

---

## Core problem & users

**Problem:** people capture information continuously (screenshots, voice notes, articles, clipboard) but the recall layer is broken — you remember "I saw a chart about X last week" but can't find it.

**Users:** knowledge workers, researchers, students. Single-user product first; multi-user is a later concern.

**Hard part:** multimodal indexing (text + image + audio) with a single query interface that returns answers grounded in citations to the original capture.

---

## Architecture (high-level)

```
Capture clients          →  Ingestion pipeline   →  Index            →  Retrieval API     →  Answer service
─────────────────           ─────────────────        ─────             ─────────────         ───────────────
• browser ext (web pages)   • screenshot → VLM      • dense vectors   • hybrid search       • LLM with citation
• menu-bar capture          • voice memo → ASR      • sparse (BM25)   • reranker            • answer faithfulness
  (screenshot, clipboard)   • text → chunker        • metadata DB     • candidate fusion      check
• voice memo recorder       • dedupe + entity tag                                           • streaming response
```

**Trained components (pick one for v1):**
1. Fine-tuned bi-encoder retriever on synthetic query/doc pairs derived from your own corpus
2. Fine-tuned cross-encoder reranker on the same data
3. VLM-distilled screenshot understander (small model that outputs structured descriptions)

v1 should pick **one** and benchmark against a strong zero-shot baseline (e.g. `bge-large-en-v1.5`, Cohere rerank, GPT-4V).

**Stack candidates:**
- Vector DB: Qdrant (local) or LanceDB (file-based)
- ASR: WhisperX or Parakeet
- VLM for screenshots: Qwen2-VL 7B or moondream
- Capture client: Tauri (Rust+web) or Electron, or native Swift for menu-bar (Mac-only)
- Training: Sentence-Transformers + PEFT on cloud GPU

---

## Evaluation harness (the differentiator)

**Build TWO eval sets:**

1. **Retrieval eval** (BEIR-style)
   - 50–100 hand-crafted queries against your indexed corpus
   - Ground-truth relevant document IDs marked
   - Metrics: nDCG@10, MRR, recall@k, P@k
   - Run baseline vs your fine-tuned model on every PR

2. **End-to-end QA eval**
   - 50 questions where the correct answer requires citing a specific captured item
   - Judge: GPT-4 as judge with structured rubric (factuality, citation correctness, completeness)
   - Metrics: answer accuracy, citation precision/recall, hallucination rate

**Operational metrics tracked per query:**
- Latency P50/P95/P99 (ingest, retrieve, rerank, generate)
- Cost (tokens in/out, API calls)
- Index size growth over time

---

## Partner ownership split (if continued as 2-person)

- **One owns:** capture clients + ingestion pipeline + multimodal extraction (VLM/ASR integration)
- **Other owns:** retrieval engineering + training/fine-tuning + eval harness
- **Shared:** answer service, API contract, benchmark writeup

---

## v1 scope (10-week target)

In:
- Text + screenshot ingestion (skip audio for v1)
- Hybrid BM25 + dense retrieval, no reranker yet
- Single capture client (menu-bar only)
- Retrieval eval suite with 50 queries
- Baseline vs one trained variant (retriever fine-tune)
- FastAPI service, simple web UI for query

Out (deferred to v2):
- Voice memo ingestion
- Reranker
- Browser extension
- End-to-end QA eval
- Multi-user

---

## UAE relevance

Strong — G42 / Core42 / Presight AI all work on RAG over sovereign data. Arabic-English bilingual retrieval would be a real differentiator. If pursuing UAE positioning, extend the eval set to include Arabic queries + Arabic-OCR'd documents.

---

## Reading list (build before starting)

- BEIR paper (Thakur et al. 2021)
- "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks" (Lewis et al.)
- ColBERT / ColBERTv2 papers (late interaction)
- Sentence-Transformers documentation, fine-tuning guide
- LangChain / LlamaIndex source — read, don't depend on (CV: own your architecture)
- Pinecone / Qdrant production architecture docs

---

## Red flags to avoid

1. Using LlamaIndex as a black box — you must own the retrieval logic
2. Skipping the eval set because "it's obviously better"
3. Claiming "multimodal" when you only handle text well
4. Over-indexing on UI polish before the retrieval works
5. Comparing only against your own zero-shot baseline — must include a strong public baseline (BGE, Cohere)
