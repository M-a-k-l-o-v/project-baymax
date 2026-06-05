# ROADMAP — BAYMAX v1 and v2

**Drafted:** 2026-05-16
**Working assumption:** 4.5 months full-time over summer (May 18 – Oct 1), then term-time + part-time job
**Hard deadlines:** v1 demo Jul 26 · v2 demo Sep 6 · portfolio-ready Oct 1

---

## Phase 0 — Scaffolding (Week 1: May 18-24)

**Goal:** repo is a healthy place to work. No features yet.

Deliverables (both):
- Old subprojects (`voice Interactive chat bot/`, `Virtual_space_constructor/`, `listening agent/`) deleted or archived to `archive/`
- `task manager/` renamed to `task_manager/`, imports fixed
- Root `pyproject.toml` with `uv` or `poetry`, single venv
- `ruff` + `pyright` + `pytest` configured
- GitHub Actions: lint + typecheck + test on every PR
- Branch protection on `main`, PR review required, squash-merge only
- `.env.example`, secrets out of source
- New layout established:
  ```
  src/baymax_core/
  src/baymax_tools/
  src/baymax_models/
  src/baymax_eval/
  src/baymax_service/
  scenarios/
  experiments/ results/
  tests/unit/ tests/integration/
  docs/
  scripts/
  ```

Phase 0 exit criteria:
- Both partners merged ≥2 PRs each
- CI green on `main`
- `PROBLEM.md`, `OWNERSHIP.md`, `ARCHITECTURE.md` (first draft), `ROADMAP.md` committed
- README rewritten to describe new project

---

## Phase 1 — v1 baseline (Weeks 2-5: May 25 – Jun 21)

**Goal:** end-to-end skeleton with naive agent + 50 scenarios + baseline numbers.

### Marv (Person 1)
- Week 2: Tool-call contract (JSON schema, owned ADR), naive agent core that picks tools via prompted GPT-4
- Week 3: FastAPI service exposing `/invoke` endpoint, async tool execution, request tracing
- Week 4: Telemetry — structured logs, OpenTelemetry traces exported to local Jaeger or file
- Week 5: First pass at recovery (retry on rate limit, refusal on out-of-scope)

### Ronin (Person 2)
- Week 2: Scenario format (JSON schema, owned ADR), first 15 scenarios across Notion + Calendar
- Week 3: Scenario runner + first metrics (tool-call match, task success), Notion adapter
- Week 4: Gmail + Calendar adapters, 35 more scenarios, baseline run vs GPT-4
- Week 5: LLM-as-judge protocol for ambiguous cases, baseline vs Claude run

Phase 1 exit criteria (Jun 21):
- 50 scenarios in `scenarios/v1/`
- Eval harness produces `results/v1-baseline.json` with task success, tool-call accuracy, latency, cost
- Naive agent baseline numbers published in `BENCHMARKING.md`
- One demo video (3 min) of a happy-path scenario

---

## Phase 2 — v1 polish + first trained model (Weeks 6-10: Jun 22 – Jul 26)

**Goal:** ship a fine-tuned local model that beats baseline on ≥1 metric.

### Marv
- Week 6: Inference service supports swappable backend (OpenAI API vs local MLX); model registry interface
- Week 7: Streaming inference, latency budget per stage, P50/P99 tracking
- Week 8: Cost tracker, per-tenant rate limits
- Week 9-10: Polish: error UX, clarification turns, integration tests

### Ronin
- Week 6: Data prep pipeline (scenarios → SFT format), train/eval split with no leakage
- Week 7: First SFT run on Qwen 2.5 1.5B (cloud GPU rental — RunPod ~$30 budget)
- Week 8: Ablations (LoRA rank, data mix, instruction template)
- Week 9-10: Eval re-run against fine-tuned model, write `BENCHMARKING.md` results section

Phase 2 exit criteria (Jul 26):
- v1 demo video (5 min) covering one scenario per tool
- Fine-tuned model checkpoint in registry, served via MLX on Mac
- Benchmark shows fine-tuned model beats baseline on ≥1 metric (target: cost per task ≥10× lower with comparable accuracy)
- `BENCHMARKING.md` published with full result tables and methodology

---

## Phase 3 — v2 expansion (Weeks 11-16: Jul 27 – Sep 6)

**Goal:** harder scenarios, multi-turn, telemetry dashboard, ablation study.

### Marv
- Multi-turn dialog state (memory across turns within a session)
- Recovery from tool failure (Notion 5xx, calendar conflict, etc.)
- Telemetry dashboard (Grafana or simple custom UI) reading from trace store
- Cancellation + barge-in (optional stretch)

### Ronin
- 150 more scenarios (total 200), including multi-turn and ambiguous intent
- Ablation study: which components earn their keep (RAG? fine-tuning? structured output?)
- Second model variant (3B?) with comparison
- Failure taxonomy from eval runs → drives Marv's recovery work

Phase 3 exit criteria (Sep 6):
- v2 demo video (8 min) covering multi-turn + recovery
- Ablation study written up in `docs/ablations.md`
- Telemetry dashboard demoable
- 200 scenarios, eval suite repeatable in CI nightly

---

## Phase 4 — Polish + outreach (Weeks 17-19: Sep 7 – Oct 1)

**Goal:** project is portfolio-ready. Start outreach.

Both:
- Final writeup (blog post, ~2500 words, technical with diagrams)
- Demo video re-recorded with polish
- README rewritten as a portfolio artifact (problem, approach, results, next steps)
- CV bullets drafted per CV Segment 2 format: exact technical problem, exact stack, exact ownership, exact scale, exact result
- Each partner sends first 10 outreach emails per the CV's outreach playbook (5 high-quality reaches per week starting now)

Phase 4 exit criteria (Oct 1):
- Repo is publicly demoable to a senior engineer with zero hand-holding
- Both CVs updated with BAYMAX bullets
- At least 20 outreach contacts made
- Decision committed: continue BAYMAX (v3 stretch) or freeze and shift to TADASHI-1

---

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Scope creep ("let's add agent X") | OWNERSHIP doc + ROADMAP doc — any scope change requires a PR amending both, with the deferred scope moved to `future_work/` |
| Fine-tuning underperforms baseline | Pivot to: ensemble baseline + small model for routing, or distillation from GPT-4 traces. Document the pivot honestly. |
| Tool API changes mid-project (Google deprecates something) | Tool adapter contracts versioned independently of agent core |
| One partner falls behind | Weekly sync (Mon 30 min). If behind by ≥3 days on a milestone, re-scope at the sync, don't paper over. |
| Burnout (4.5 months full-time is long) | One full day off per week, mandatory. No commits on that day. |
| TADASHI-1 starts pulling attention | TADASHI-1 does not start until v1 is shipped (Jul 26). Period. |

## What this roadmap is not

- Not a schedule for a manager to track. There is no manager. The two of you enforce it on each other.
- Not a contract with future-you. Quarterly re-plan based on what you learn.
- Not exhaustive. Many tactical decisions happen weekly inside the phases.

## Cadence

- Mon 09:00: 30 min sync (last week, this week, blockers)
- Wed 09:00: 15 min standup (status only)
- Fri afternoon: PR review backlog cleared, week's metrics published to `results/`
- Sat: optional. Sun: hard day off.

## Parallel commitments (transparency)

So the partner knows what else is in the time budget — and can flag if BAYMAX milestones slip because of it.

**Marv:**
- ML foundations self-study to prep for SCCM6230 (Jan 2027): ~30 hours total across 5 weekends, Jul 11 – Sep 6. Sized to fit between BAYMAX phases without disrupting milestones. Tracked in a local-only plan, not committed to this repo.
- TADASHI-1 (individual robotics flagship): does NOT start until after BAYMAX v1 ships (Jul 26). No competing time before then.

**Ronin:**
- (add own parallel commitments here so Marv has the same visibility)
