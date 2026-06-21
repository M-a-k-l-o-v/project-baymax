# BAYMAX Writeup — Hypothesis, Success Criteria, and the Reframe

Notes captured from the design discussion. Source material for the eventual public blog post / CV bullet articulation. Reads as a "why this project exists and what it measures" doc.

---

## The trap to avoid

If the hypothesis were *"Qwen beats GPT-4"* we'd lose, and the project would be silly. That is **not** the hypothesis.

## The real hypothesis (one sentence)

> For a narrow, well-specified personal-task domain with a fixed tool surface (4 tools, ~100 scenario types), a small (1.5B) fine-tuned local model can match frontier-model task-success rate while delivering ~1000× lower cost, ~2-4× lower latency, and full data privacy.

That's the research question. Notice what it doesn't claim:

- It doesn't claim Qwen is "smarter" than GPT-4
- It doesn't claim Qwen generalizes better
- It doesn't claim Qwen works outside the trained domain

It claims something very specific: **on the narrow slice of behavior we've trained for, can specialization close the capability gap enough that the cost/latency/privacy wins become real?**

---

## Why this thesis matters in 2026

This is one of the most active research questions in applied AI right now:

- **Apple Intelligence** is built on this thesis — small on-device models do narrow tasks, route hard tasks to the cloud
- **Google Gecko / Gemini Nano** — same thesis
- **Physical Intelligence's π0-FAST** (the tadashi-2 direction) — same thesis applied to robot policies
- **Specialized vertical agents** at every AI startup — same thesis applied to legal / medical / finance
- **Mistral / Cohere / Hugging Face** entire business model — same thesis

The *"small specialist beats frontier generalist on narrow domain"* claim is the central engineering bet of the on-device AI era. Embodied AI companies care about this because they can't ship a robot that needs to round-trip to GPT-4 for every action — too slow, too expensive, no privacy.

---

## What "success" looks like — multiple definitions

You don't need one binary outcome. The eval produces a frontier curve, and several outcomes count as wins:

### Strong positive (best case)

- Qwen fine-tuned reaches ≥90% of GPT-4's task-success rate on the eval
- At ~1000× lower cost
- **CV bullet:** *"Fine-tuned 1.5B model matches 91% of GPT-4 accuracy at 0.1% of the cost"* — strong

### Moderate positive

- Qwen reaches ≥80% of GPT-4 overall
- But hits ≥95% on specific scenario classes (direct tool calls, easy cases)
- Underperforms on multi-step / clarification scenarios
- **CV bullet:** *"Characterized the capability frontier — fine-tuned small model dominates on direct tool calls (95%) but drops to 62% on multi-step reasoning. Proposed and demonstrated hybrid routing where small model handles 80% of traffic at 0.1% cost, escalates remaining 20% to GPT-4."*

This is actually the **most defensible outcome** — it shows real engineering judgment.

### Negative result (still valuable)

- Qwen fine-tuned underperforms across the board
- Eval honestly documents WHERE and WHY
- Ablations identify which interventions help and which don't (LoRA rank, data size, instruction template)
- **CV bullet:** *"Demonstrated that 100 scenarios is insufficient SFT data for closing the 1.5B-vs-frontier gap on multi-step agent tasks. Quantified the gap, identified the failure modes, and characterized the data-scaling requirement (extrapolated ~2000 scenarios needed for parity)."*

This is **still a hireable result.** Negative results that are well-measured are exactly what good research looks like.

### Catastrophic failure (only real failure mode)

- Eval harness is buggy, results are unreliable, no conclusions can be drawn
- Avoidable with discipline

**So three of four outcomes are CV wins. The only way to fail is bad methodology.**

---

## What we hope to see, concretely

The numbers we're rooting for, as a target:

| Metric | Qwen fine-tuned target | Why this number |
|---|---|---|
| Task success rate | ≥85% of GPT-4's | Above this, the cost/latency win clearly compensates |
| Tool-call accuracy | ≥90% of GPT-4's | Tool selection is easier than full reasoning |
| Hallucination rate | ≤2× GPT-4's | Schema validation catches most, but model-level shouldn't be 10× worse |
| Cost per task | ≤$0.001 | GPT-4 is $0.005-0.015, so 5-15× cost win minimum |
| Latency P99 | ≤500ms first token | Real-time conversational feel |

If you hit those, the thesis is validated. If you don't, the **frontier curve showing how you fell short is itself the result.**

---

## The reframe — the eval IS the thesis

The point worth internalizing: **the project's value is not the Qwen fine-tune. The project's value is the measurement apparatus** that can answer "small-specialist-vs-frontier-generalist" questions in general.

Once you have it:

- You can swap Llama 3.2 1B in and see how it compares
- You can swap distilled GPT-4 outputs as training data and see if that closes the gap
- You can swap a different scenario set (medical, legal, finance) and run the same comparison
- You can answer "is RAG over scenarios enough?" without fine-tuning at all

Every one of those is a separate experiment runnable in days, producing comparable numbers. That's the long-tail value the CV cares about — not whether one specific Qwen fine-tune happened to beat GPT-4 once.

---

## The interview answer

Senior engineer asks *"why do this when GPT-4 is better?"* — the answer:

> *"GPT-4 is better at the task. The question we're answering is: under what conditions does a 1.5B specialist close the gap enough to be the right production choice — cheaper, faster, private? The harness is what answers that, and the Qwen run is the first experiment we ran with it."*

That's defensible. *"We tried to beat GPT-4 with a small model"* is not.
