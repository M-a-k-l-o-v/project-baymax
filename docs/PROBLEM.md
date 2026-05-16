# PROBLEM — what BAYMAX is and what it is not

**Drafted:** 2026-05-16
**Owners:** Marv + Ronin
**Status:** working draft — review and edit before locking

---

## The problem in one paragraph

A solo knowledge worker uses Notion (tasks), Google Calendar (meetings), Gmail (correspondence), and the system clipboard (clips/snippets) every day. Most micro-orchestration between these tools is mental overhead: "make a task from this email," "book 30 min tomorrow on the X project," "remind me about the article I just copied." Existing "AI assistants" attempt this badly — they hallucinate tool calls, have no measured task success rate, and are tested on one-off demos rather than reproducible scenarios.

## What BAYMAX v1 is

A locally-hostable agent that:
1. Accepts voice or text input describing a productivity task
2. Selects and executes a sequence of tool calls (Notion, Calendar, Gmail, clipboard)
3. Confirms or asks for clarification
4. Logs every action with a trace ID for audit

…and is **evaluated** against a reproducible benchmark suite of ≥100 scripted task scenarios with measured task success rate, tool-call accuracy, hallucination rate, latency P50/P99, and cost per task.

The defining property is the **eval suite**, not the agent itself.

## What BAYMAX v1 is NOT

Anti-claims, written down so we don't drift:

- Not a "general personal assistant." Scope is the four tools listed above. Out of scope: web browsing, code execution, document writing, image generation, ride-booking, anything not in the tool list.
- Not a multi-agent orchestration framework. One agent process. No "TaskAgent + CalendarAgent + FinanceAgent" sprawl — that was the original BAYMAX direction and is deliberately discarded.
- Not a wrapper that just calls GPT-4. The fine-tuned local model is a v1 deliverable, not a v2 stretch.
- Not a voice-UX product. Voice is one input modality; the agent and eval are text-first.
- Not benchmarked only against itself. Every metric is reported alongside a strong public baseline (GPT-4 / Claude / Llama-3.1-70B-via-API).

## Why this is a defensible AI Systems flagship

Checks every box from the Tadashi CV Segment 2 "AI systems flagship" template:

- ✅ train + evaluate + deploy pipeline
- ✅ real dataset (the scenarios + tool-call traces are the dataset)
- ✅ reproducible experiments (scenario suite, fixed seeds, versioned model checkpoints)
- ✅ tracked metrics (task success, tool-call accuracy, latency, cost)
- ✅ inference API or edge deployment (local MLX/llama.cpp on Mac)
- ✅ clear research question: *"Can a fine-tuned small open-weights model match a frontier LLM on a constrained personal-task domain at ≥10× lower latency and ≥50× lower cost per task?"*

## Hard problems we will actually solve

These are the parts that make this engineering, not a wrapper:

1. **Tool-call contract that is deterministically replayable** — given a scenario and a model version, the same trace must reproduce
2. **Eval that handles ambiguity** — multiple valid tool-call sequences for the same intent; LLM-as-judge with a structured rubric
3. **Latency budget under streaming** — partial results, async tool execution, cancellation
4. **Fine-tuning that actually beats baseline on the eval** — data prep, ablation discipline, no leakage between train and eval scenarios
5. **Refusal and clarification** — the agent must refuse out-of-scope tasks cleanly, and ask clarifying questions when intent is underspecified

## Users (initial)

Two: you and your partner. Real usage on real Notion/Calendar/Gmail/clipboard. Self-dogfooding is mandatory — if you wouldn't use the v1 yourselves daily, we haven't built v1.

## What "done" looks like for v1 (Jul 26)

- 50 scripted scenarios in `scenarios/v1/` covering create/query/update/refuse across the four tools
- Eval harness runs end-to-end, outputs metrics JSON
- Naive baseline (GPT-4 via API + Claude API) measured
- Fine-tuned model (Qwen 2.5 1.5B or similar) deployed via MLX on Mac
- Fine-tuned model beats baseline on ≥1 metric (target: cost per task ≥10× lower, with comparable accuracy)
- 5-minute demo video covering one scenario per tool
- README + ARCHITECTURE + BENCHMARKING docs published

## What "done" looks like for v2 (Sep 6)

- 200 scenarios including multi-turn, recovery from tool failure, ambiguous intent
- Streaming inference, latency budgeted and tracked
- Telemetry dashboard (cost, latency, success rate over time)
- Ablation study: does each component (RAG, fine-tuning, structured output) earn its keep?
- Public technical writeup published (blog post + video walkthrough)
