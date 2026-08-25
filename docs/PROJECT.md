# PROJECT — What BAYMAX is (and isn't)

**Framing lock (2026-08-24)**: BAYMAX is a **stepping-stone learning project**. It is not a research contribution, not a daily-driver personal assistant, and not the primary CV flagship. It's a shipped, evaluated, honestly-documented tool-use agent that demonstrates engineering competence and methodology discipline. That's it. That's the artifact.

Consolidated from prior `PROBLEM.md` + `WRITEUP_INFO.md` + `METHODOLOGY.md` (all removed 2026-08-24; content that mattered is here, rest was publication-review overhead).

---

## 1. What BAYMAX is

A locally-runnable personal-task agent that:

1. Accepts text input describing a productivity task (calendar / notion / gmail / clipboard territory)
2. Selects and executes a sequence of tool calls against fake in-memory adapters (calendar, notion, gmail, clipboard)
3. Confirms, refuses, or requests clarification when needed
4. Logs every action with trace / task identifiers
5. Is evaluated against a scripted benchmark suite (v1: 50 scenarios; may grow modestly)

Backed by a fine-tuned Qwen 2.5 1.5B + LoRA served via MLX on a Mac (Marv-side) OR an OpenAI backend (baseline).

The **defining artifact** is the eval-driven agent + shipped repo, not any specific model win.

## 2. What BAYMAX is NOT

- **Not a daily-driver personal assistant** — fake adapters only, no OAuth to real Google / Notion, response quality too low to trust with real actions. Making it useful for real daily use would need 2-3 months more focused work (real adapters + bigger model + menu-bar UI + safety guardrails). Not on the roadmap.
- **Not a research contribution** — the "small model + SFT for tool use" question has been researched extensively (xLAM 2024, ToolLLaMA 2023, Gorilla 2023, NexusRaven 2023). BAYMAX is a competent execution of a well-explored area, not novel.
- **Not the primary CV flagship** — that's TADASHI-1 (robotics). BAYMAX is portfolio evidence of engineering + methodology discipline; TADASHI-1 is the research signal.
- **Not a workshop / paper submission target** — see §5 writeup plan.
- **Not benchmarked as "small model beats frontier"** — that framing was rejected. See §4 comparison framing.

## 3. What the project actually measures

**Honest hypothesis (2026-08-24 framing):**

> Given a small fine-tuned model (Qwen 1.5B + LoRA), trained on frontier-derived generic tool-use data (Salesforce/xLAM-function-calling-60k), and evaluated on BAYMAX-specific scenarios via an output-adaptation layer, characterize what fraction of a frontier baseline's task-success rate the fine-tune achieves and enumerate the failure modes.

Expected outcome: fine-tune underperforms gpt-4o-mini baseline. Current smoke-test result: 0.24 vs 0.52 baseline. Proper training runs may improve to 0.35-0.50 range. **This is the honest outcome — not a project failure.**

## 4. Methodology essentials

Stripped down from prior publication-review-flavored discipline. What still matters:

- **Author-split discipline**: Marv owns runtime / backend / adapter. Ronin owns data / training / eval. Neither influences the distributional shape of the other's work based on knowledge of their own. Prevents distributional overfitting; keeps the headline number honest.
- **External training data**: Salesforce/xLAM-function-calling-60k, version-pinned. NOT same-author-as-eval training scenarios.
- **Output adapter**: translates fine-tuned model emissions (xLAM format) to BAYMAX's `AgentResponse` shape. Designed from tool schema, not from eval scenarios.
- **Basic tiered eval**: in-distribution + small OOD subset. Report both; don't aggregate into a single number.
- **Basic statistical honesty**: sample size disclosed alongside every headline number. Comparison claims phrased proportionally to sample size.
- **Comparison framing**: use one of A/D from below; NEVER head-to-head "small beats frontier."

### Defensible comparison framings

| Framing | Comparison | Notes |
|---|---|---|
| **A. Fine-tune vs its own base** | Qwen 1.5B untuned vs Qwen 1.5B + fine-tune | Measures fine-tuning delta cleanly |
| **C. Cost-normalized** | gpt-4o-mini $/scenario vs local Qwen ≈ $0 | "N% quality at 0% cost" |
| **D. Transfer-learning characterization** ⭐ | Characterize how far external-data training gets on a domain-specific contract | Matches chosen approach; honest |
| ~~E. Head-to-head~~ | Fine-tune vs frontier | Rejected — specialist vs generalist unfair |

Current headline claim: **A + D reported honestly**. Neither requires the fine-tune to win.

## 5. Writeup plan

**No workshop paper chasing.** Publication tier for BAYMAX:

- **arXiv preprint** — post regardless. Free, immediate, citation-able.
- **Blog post** — 2500-word technical writeup on personal site. Aim for /r/MachineLearning frontpage.
- **HuggingFace model card + adapter publication** — Ronin uploads the fine-tuned Qwen adapter with methodology writeup as the model card. Industry-visible artifact.
- **CV bullet** per Tadashi CV Segment 2 format: exact technical problem, exact stack, exact ownership, exact scale, exact result.

Everything above earns its keep for portfolio + Master's application evidence. NeurIPS/ICLR workshops or main-track submissions do not.

## 6. Honest limitations (for the writeup + repo)

When talking about BAYMAX publicly:

- Fake adapters only — no real integration with Google / Notion / Gmail / system clipboard
- Small model — Qwen 1.5B, tiny by 2026 standards
- Small eval — 50-200 scenarios; underpowered for strong statistical claims
- Single-user, single-machine scope
- No streaming, no multi-turn dialog, no state persistence across requests
- Expected fine-tune underperformance vs frontier baseline
- No production deployment story (uvicorn manual start; no menu bar app)

All of the above are documented deliberately, not hidden. See `DEFERRED.md` for the full list with revisit triggers.

## 7. Users

**Two builders**: Marv + Ronin. **Not real end-users.** Self-dogfooding for evaluation is optional; the eval scenarios are the primary quality signal.

## 8. Team ownership (brief)

| Module | Owner |
|---|---|
| Agent core, inference service, telemetry, MLXBackend, output adapter | Marv |
| Eval harness, training pipeline, tool adapters, scenario authorship | Ronin |
| Shared: repo scaffolding, ARCHITECTURE.md, writeup, demo | both |

Full ownership rules and PR protocol: [OWNERSHIP.md](OWNERSHIP.md).

## 9. Related docs

| Doc | Purpose |
|---|---|
| [ROADMAP.md](ROADMAP.md) | Realistic timeline to stepping-stone ship (~5 weeks from 2026-08-24) |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System design |
| [OWNERSHIP.md](OWNERSHIP.md) | Module ownership + PR rules |
| [BACKEND_FLOW.md](BACKEND_FLOW.md) / .html | Backend + agent design diagrams (post-ADR 0011 target) |
| [BENCHMARKING.md](BENCHMARKING.md) | Eval methodology + results (Ronin) |
| [SCORING.md](SCORING.md) | Deterministic scoring rules (Ronin) |
| [DEFERRED.md](DEFERRED.md) | Known limitations + not-implemented items |
| [decisions/](decisions/) | ADR archive |

## 10. Meta

This project is Marv's genuine engineering + methodology-discipline artifact for Canadian Master's applications (Dec 2026 - Feb 2027 deadlines) and industry interviews. It ships in stepping-stone scope by end of September 2026 and then Marv moves to the next `future_work/` project. Not designed to be evolved further post-ship.
