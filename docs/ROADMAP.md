# ROADMAP — BAYMAX ship (stepping-stone scope)

**Framing lock (2026-08-24)**: BAYMAX is being wrapped up as a stepping-stone learning artifact — see [PROJECT.md](PROJECT.md). This roadmap is the realistic 5-week path from today (2026-08-24) to shipped + written up + moved on.

**Ship target**: end of September 2026 (~5 weeks). Portfolio-ready state — arXiv preprint + blog post + HF model card + shipped repo + honest limitations documented.

**No more publication-review overhead.** No ablation sweep discipline, no bootstrapped-CI reporting requirements, no pre-registered failure criteria. Ship the artifact, document honestly, done.

---

## Weekly plan

### Week 1 — Aug 24-31: Documentation + ADRs + implementation start
**Marv:**
- Convert reasoning bullet-prompts to prose in ADRs 0005/0006/0007/0009/0010/0011/0012 (~1-2 hours total at documentation depth)
- Batch-commit all 7 ADRs on a branch → PR to main
- Send Ronin the ADR 0012 delta report (naming, config_hash, run_id vs model_id, MLX conversion plan)
- Start MLXBackend implementation scaffold

**Ronin:**
- Kick off the real training run (not the smoke test)
- Continue infrastructure work he's already doing on `feat/phase1-scenario-loader`
- Confirm the ADR 0012 open items (naming convention, dropped fields)

### Week 2 — Sept 1-7: Backend implementation + retry / warmup / error surfacing
**Marv:**
- `BackendError` + `ErrorType.BACKEND_ERROR` enum
- Base class `_call_llm` with retry logic (hardcoded N=3, no sweep)
- `FakeBackend` for unit tests
- Registry loader (`src/baymax/core/registry.py`)
- `MLXBackend` implementation (needs weights downloaded — HAVE_MLX=1)
- Output adapter (translates xLAM emissions → BAYMAX AgentResponse)
- Warmup scenario JSON + wiring
- Backends factory dict + lifespan updates in `api.py`

**Ronin:**
- First proper training run completes
- Optionally: one basic hyperparameter variant (bigger LoRA rank OR different data mix — NOT a full sweep)
- Register the fine-tuned model in `models/models.json`

### Week 3 — Sept 8-14: End-to-end integration + eval
**Marv:**
- Wire MLXBackend + adapter + registry into the FastAPI service
- Run integration tests (Marv-local, HAVE_MLX=1)
- Fix any last-mile issues

**Ronin:**
- Run eval end-to-end on the fine-tuned model via MLXBackend
- Produce final `results/v2-qwen-lora-final.json`
- Optionally: expand eval to 100-150 scenarios if it takes < 1 day (skip if it slips)

**Both:** BENCHMARKING.md updated with final numbers.

### Week 4 — Sept 15-21: Writeup drafting
- **Blog post draft** (~2500 words, technical) — jointly authored; Marv leads engineering sections, Ronin leads training + eval sections
- **arXiv preprint** — formatted-up version of the blog post; `cs.CL` + `cs.LG` cross-list
- **HuggingFace model card** — Ronin uploads Qwen adapter with methodology writeup as model card
- **Demo video** (~5 min) covering one scenario per tool, one round-trip on OpenAI + one on Qwen fine-tune

### Week 5 — Sept 22-28: Polish + ship
- **Repo polish** — README audit, remove dead code, ensure `pytest` green on fresh clone, docs cross-links working
- **CV bullets** drafted per Tadashi CV Segment 2 format
- **Final commit + tag** as `v0.1.0` or `stepping-stone-ship`
- **Marv moves on to next `future_work/` project**

---

## What's OUT of scope for the stepping-stone ship

Explicitly NOT part of this roadmap (don't get pulled in):

- Real API adapters (Google Calendar / Notion / Gmail / clipboard)
- Larger model (Qwen 7B+)
- Streaming inference
- SQLite state store implementation
- Menu bar app / voice / chat UI
- Multi-turn dialog
- LLM-as-judge scoring implementation
- OpenTelemetry migration
- Full LoRA rank / data mix / instruction template ablation sweep
- Compositional held-out scenario splits
- Adversarial scenario subset
- Retry-sensitivity sweep infrastructure
- Nightly integration test scheduling
- Workshop / conference paper submission

Everything in [DEFERRED.md](DEFERRED.md) stays deferred.

---

## Non-BAYMAX parallel commitments (transparency)

Alongside BAYMAX ship:

**Marv:**
- Canadian Master's application prep (earliest deadline: UofT MScAC Dec 1, 2026). SoP drafts + recommender asks in September. See `future_work/masters_program_targets.md`.
- Lancaster Year 3 starts ~Sept 22; reduces weekly BAYMAX capacity from ~Sept 22 onwards.
- Once BAYMAX ships: move to next `future_work/` project (candidates: TADASHI-1 flagship, Marbles-1 replication, open3d reconstruction, etc.)

**Ronin:**
- (add own parallel commitments here)

---

## Cadence

- Sync as needed via existing channels; no formal weekly meeting overhead
- Marv-Ronin joint updates when there's actual state change (training run complete, eval numbers in, PR ready)
- Push cadence: PRs when work is ready, not on a schedule

---

## References

- [PROJECT.md](PROJECT.md) — what BAYMAX is (and isn't); framing lock
- [ARCHITECTURE.md](ARCHITECTURE.md)
- [OWNERSHIP.md](OWNERSHIP.md)
- [BACKEND_FLOW.md](BACKEND_FLOW.md) — post-ADR-0011 backend design diagrams
- [DEFERRED.md](DEFERRED.md) — known limitations
- [decisions/](decisions/) — ADR archive (12 ADRs)
- [RONIN_SYNC.txt](../RONIN_SYNC.txt) — current sync agenda (gitignored)
- `future_work/masters_program_targets.md` — Canadian Master's application timeline (gitignored)
