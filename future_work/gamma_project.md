# Project Brief — Option γ: Speech-First Vertical Dialog Agent

**Status:** future work · not active
**Drafted:** 2026-05-16
**Predecessor concept:** the `voice Interactive chat bot/` prototype, scoped down to one vertical

---

## One-line statement

A streaming-ASR + RAG-grounded + safety-filtered conversational agent for a single high-value vertical (recommended: bilingual Arabic-English domain Q&A), evaluated on a domain-specific scenario suite with measured groundedness, latency, and refusal correctness.

---

## Why this is a defensible flagship

Hardest of the three options. Highest interview-defensibility *if* executed well — because senior engineers respect the gap between "voice + LLM demo" and "production dialog system with safety + grounding + eval."

| Criterion | How γ satisfies it |
|---|---|
| Train + eval + deploy pipeline | Fine-tuned intent classifier or safety filter, eval suite, deployed streaming service |
| Real dataset | Domain corpus (legal/medical/financial/educational) + scripted dialog scenarios |
| Reproducible experiments | Versioned scenarios, deterministic replay, fixed model snapshots |
| Tracked metrics | Groundedness, refusal correctness, latency, WER, turn-completion rate |
| Inference API | Streaming WebSocket/gRPC service with VAD + barge-in |
| Clear research question | "Can a domain-tuned small model with strict grounding match a frontier LLM on vertical-specific dialog with 10× lower latency?" |

---

## Why this is the riskiest of the three

- Streaming ASR + dialog turn-taking + barge-in + grounded generation is **four hard subsystems**, all interacting
- Safety/refusal correctness is hard to evaluate without a domain mentor
- "Pick a vertical" is itself a research decision that gates everything else
- Voice UX is unforgiving — small latency regressions break the experience

**Do not start this unless:**
- You have a domain expert available for ground-truth labeling
- You've already shipped one AI Systems flagship (e.g. α or β)
- You have GPU access (streaming ASR + inference is more compute-heavy than retrieval)

---

## Core problem & users

**Problem:** typing is the wrong input for many vertical use-cases (driving, hands busy, accessibility, fast triage). Generic voice assistants hallucinate in vertical domains and don't refuse when they should.

**Users:** vertical-specific (e.g. clinicians doing triage, lawyers checking case precedents, traders asking market questions, students in language-learning).

**Hard part:** turn-taking with low latency, grounded answers under uncertainty, calibrated refusals when out-of-domain or low-confidence.

---

## Architecture (high-level)

```
Client                       Streaming service                       Backends
──────                       ─────────────────                       ────────
• mic capture                • VAD (silero-vad)                      • retrieval (domain corpus)
• partial transcript UI      • streaming ASR (Parakeet/Whisper)      • safety filter / refusal model
• TTS playback               • intent classifier (fine-tuned)        • LLM (frontier API or local)
• barge-in detection         • dialog state machine                  • TTS (Piper / ElevenLabs)
                             • grounding check before TTS
                             • turn timing + barge-in handling
```

**Trained components (v1 picks one):**
1. Intent classifier: small encoder (DeBERTa-v3-small or similar) fine-tuned on domain utterances
2. Safety/refusal classifier: detects out-of-domain or harm requests
3. Grounding scorer: scores whether a candidate answer is supported by retrieved evidence

---

## Vertical selection criteria

Pick a vertical that:
- Has a clean public corpus (FDA labels, case law, financial filings, language-learning materials)
- Has a clear refusal/safety boundary ("I can't give legal advice — here's what the document says")
- Maps to a hiring market you care about

**Three concrete shortlist candidates:**

1. **Bilingual Arabic-English government services Q&A** (UAE-aligned)
   - Corpus: UAE government service docs (publicly published)
   - Refusal cases: medical, legal advice
   - UAE differentiator: bilingual + RTL handling + Modern Standard Arabic

2. **Language-learning conversation tutor** (broad market)
   - Corpus: graded readers, grammar references
   - Refusal cases: non-language requests
   - Strong eval: scripted learner conversations with pedagogical metrics

3. **Open-source library documentation assistant** (developer market)
   - Corpus: one large library's docs (e.g. PyTorch, ROS2)
   - Refusal cases: questions about other libraries
   - Demo-friendly, easy to share with engineers

---

## Evaluation harness

Three eval sets, all required:

1. **ASR accuracy** — WER on domain audio (clean + noisy)
2. **Dialog completion** — 50–100 scripted conversations with success criteria per turn
3. **Safety/refusal** — adversarial prompts that *should* be refused (out-of-domain, harm requests, ungrounded claims) measured for false-accept and false-refuse rates

**Latency budget tracking** — for streaming, P50/P95 of:
- ASR partial → final
- Final transcript → first generated token
- First token → first TTS audio chunk

End-to-end "voice in → voice out" P95 target: < 1500 ms for v1.

---

## Partner ownership split (if continued as 2-person)

- **One owns:** ASR streaming + VAD + TTS + turn-taking state machine + client
- **Other owns:** intent classifier + retrieval + grounding + safety + eval harness
- **Shared:** API contract, latency budget, final writeup

---

## v1 scope (10-12 week target — longer than α/β)

In:
- One vertical, one language (English) — bilingual is v2
- VAD + streaming ASR (off-the-shelf, e.g. faster-whisper)
- Fine-tuned intent classifier on 500–2000 labeled domain utterances
- Retrieval + grounding check + grounded LLM response
- Scripted dialog eval suite + ASR WER + refusal eval
- Streaming WebSocket service + simple web client

Out (deferred):
- Barge-in
- Multi-turn memory beyond current session
- TTS voice cloning
- Bilingual / RTL support
- Edge deployment

---

## Reading list (build before starting)

- Whisper paper + WhisperX repo
- "Retrieval-Augmented Generation" (Lewis et al.) — same as β
- "RAGAS: Automated Evaluation of Retrieval Augmented Generation"
- Silero VAD docs
- "Conversation as a Platform" — dialog systems chapter, Jurafsky & Martin
- Anthropic's posts on grounding + refusal training
- Production streaming ASR architectures (Deepgram blog, AssemblyAI blog)

---

## Red flags to avoid

1. Skipping VAD and trying to handle turn-taking with timeouts only
2. Claiming "low-latency" without budget tracking per stage
3. Using a generic LLM with no domain tuning and calling it a "vertical agent"
4. No refusal evaluation — this is the safety differentiator
5. Trying to do barge-in in v1 (it's a v2/v3 feature)
6. Demoing on a single rehearsed conversation instead of running the eval suite

---

## When to revisit

After α or β has shipped with real metrics. γ is the natural v3 — it builds on retrieval engineering (β) and tool/agent infrastructure (α). Starting γ first is the highest-variance choice.
