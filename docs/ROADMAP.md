# ROADMAP — BAYMAX v1 and v2

**Drafted:** 2026-05-16 · **Last major revision:** 2026-07-28 (deadline extended for research quality)
**Working assumption:** Extended timeline — quality over speed. See §Deadline stance below.
**Original hard deadlines (superseded):** v1 demo Jul 26 · v2 demo Sep 6 · portfolio-ready Oct 1
**Governing methodology:** [METHODOLOGY.md](METHODOLOGY.md) — mandatory read for all contributors (human and AI).

**System-wide open item:** SECURITY needs to be evaluated system-wide when real adapters arrive (email, calendar, etc). Tracked under Phase 3.

---

## Deadline stance (2026-07-28 update)

Original timeline (Oct 1 portfolio-ready) has been **extended** in favor of a stronger research artifact. Two triggers for the extension:

1. Realization that same-author training+eval bakes in distributional bias; needed to restructure data acquisition (external dataset + output adapter approach, see METHODOLOGY §4)
2. Realization that eval design is missing failure-mode #3 (poor generalization) coverage — needs OOD tier, adversarial subset, compositional held-out split, and 200+ scenarios before defensible comparison claims can be made

**New pacing**: soft deadlines, driven by research-quality gates rather than calendar. Master's application window (Jan-Mar 2027) is the ultimate constraint — everything must be portfolio-ready by ~Dec 2026 at latest, but Nov-Dec is the target.

**Phase progression gate**: each phase now requires a methodology audit against [METHODOLOGY.md §11](METHODOLOGY.md) before advancing. Missing tiers, missing CI reporting, or unresolved author-split issues block progression.

---

## Phase 0 — Scaffolding (Week 1: May 18-24) ✅ SHIPPED

**Goal:** repo is a healthy place to work. No features yet.

Delivered:
- Pre-pivot subprojects archived to `archive/`
- Root `pyproject.toml` with `uv`, single venv, Python 3.12
- `ruff` + `pyright` + `pytest` configured
- GitHub Actions CI (lint + typecheck + test on every PR)
- Branch protection on `main`, PR review required, squash-merge only
- `PROBLEM.md`, `OWNERSHIP.md`, `ARCHITECTURE.md`, `ROADMAP.md` committed
- README rewritten to describe new project

---

## Phase 1 — v1 baseline (Weeks 2-5: May 25 – Jun 21) ✅ SHIPPED (with adjusted scope)

**Original goal:** end-to-end skeleton with naive agent + 50 scenarios + baseline numbers.
**Actual outcome:** end-to-end skeleton + agent + 50 scenarios + baseline numbers on gpt-4o-mini shipped.

Delivered — Marv:
- Tool-call contract (ADR 0002): boundary `AgentResponse` + internal `TaskFile`
- Agent core: Plan-and-Execute + ReAct recovery (ADR 0001), validator, dispatcher, meta-tools
- Inference service: `InferenceBackend` ABC + `OpenAIBackend` (gpt-4o-mini default)
- FastAPI service: `/invoke` + `/health` with lifespan singletons
- Telemetry: `TelemetryLogger` + `CostAccumulator` with redaction (ADR 0010), ndjson traces (ADR 0006)
- Dispatcher routes to Ronin's fake adapters (calendar/notion/gmail/clipboard)
- 106 tests, CI green

Delivered — Ronin:
- Scenario schema (ADR 0003), 50 scenarios across 4 tool namespaces + COVERAGE.md
- Eval harness (`src/baymax/eval/`): scenario loader, runner, CLI, agent runner
- Base model choice (ADR 0004): Qwen 2.5 1.5B
- LLM-as-judge protocol scaffold (ADR 0008) — implementation deferred to v2
- Baseline eval run: `results/v1-agent-openai.json` — task_success_rate 0.52 on gpt-4o-mini

**Phase 1 known limitations (documented, deferred):**
- Trace format = custom JSON, NOT OpenTelemetry (OTel deferred to v2)
- Tool integrations = fake adapters only, real APIs deferred to v3+
- Clarification scenarios single-turn and terminal (multi-turn deferred)
- SQLite state store planned in ADR 0007 but NOT shipped in v1 — DOWNGRADED to v2 target on 2026-06-23; v1 runs in-memory only
- LLM-as-judge scoring deferred; v1 uses deterministic scoring only

Phase 1 scope note:
- Scenario input is text-only. Audio input is deferred to a later v3/v4-style expansion.
- Eval uses deterministic scoring for v1. LLM-as-judge scoring is deferred.
- Trace data follows the implemented custom JSON-line telemetry shape, not OpenTelemetry.
- Tool integrations use fake adapters only; real Notion, Calendar, Gmail, and clipboard APIs are deferred until fake-adapter evals are stable.
- Clarification scenarios are single-turn and terminal in v1. Sub-task chains and multi-turn clarification follow-ups are deferred.

---

## Phase 2 — Research-quality training + eval hardening (from Jun 22, open-ended timeline)

**Goal (revised 2026-07-28):** Ship a fine-tuned local model with a research-defensible characterization of transfer-learning ceiling from public tool-use data to BAYMAX's domain contract. NOT "beat baseline on ≥1 metric" — that framing was rejected in favor of the honest characterization per METHODOLOGY §1.

### Marv (runtime + adapter side)

Locked from Phase 2 design work (see [RONIN_SYNC.txt Tier B](../RONIN_SYNC.txt)):
- Backend interface v2 = template pattern per TRANSPORT (not per model). ADR 0011 to write.
- Model registry (Option A manifest at `models/models.json`). ADR 0012 to write.
- Immutable + monotonically incrementing model IDs (`v1` → `v2` → `v3`, never overwrite)
- Retry policy = exponential backoff up to N attempts on transient failures
- Warmup = backend-only, blocks `/health` until warm; uses a dedicated "warmup" scenario that exercises tool-call generation

Remaining Phase 2 work:
- Write ADR 0011 (backend interface v2) and ADR 0012 (model registry)
- Implement `MLXBackend` for local Qwen serving
- **Implement output adapter** — translation layer that converts fine-tuned model emissions (in xLAM format) to BAYMAX's `AgentResponse` shape. Designed blind to eval scenarios per METHODOLOGY §7.
- Adapter test suite (every translation case = test case)
- Backend capability declaration (open decision — enforce interface uniformity OR advertise `.capabilities()`)
- Register-time validation for `models.json` entries (required fields per METHODOLOGY §8)

### Ronin (data + training + eval side)

Delivered (from Phase 1 push):
- Data prep pipeline scaffolding, scenario schema, eval harness

Remaining Phase 2 work:
- **Training data**: source Salesforce/xLAM-function-calling-60k. Version-pin HF revision. Sample-review 5-10% for quality. Subsample to 2K-5K for LoRA. (Per RONIN_SYNC A1)
- **Coverage gap enumeration**: check xLAM for refusal / clarification / verification / `_contains` coverage. If missing, template-generate supplementary set (~100-200 examples) narrowly scoped.
- **First SFT run** on Qwen 2.5 1.5B with LoRA on cloud GPU (target ~$30 budget)
- **Ablations**: LoRA rank, data mix (xLAM only vs xLAM + supplementary), instruction template
- **Model checkpoint** → written to `models/qwen-1.5b-baymax-v1/` per METHODOLOGY §8. Manifest patch to `models.json` (AI-assisted per RONIN_SYNC B2)
- **150 new scenarios** for eval expansion (total 200) per hybrid split (RONIN_SYNC A3 pre-meeting note):
  - ~100-120 in-distribution + compositional bulk (template + LLM + spot-review)
  - ~15-20 OOD tier (hand-authored)
  - ~10-15 adversarial subset (hand-authored)
  - ~5-10 refusal/clarification/verification (hand-authored)
- **Diversity metrics** on the new batch (bucket distribution)
- **Embedding-similarity check** between generated batch and existing 50 scenarios
- **Compositional held-out plan**: identify which tool combinations to hold out from training so eval can test compositional generalization
- **Statistical reporting**: mean ± bootstrapped 95% CI on all aggregate metrics
- **Pre-registered failure criterion**: written to `docs/experiments/<experiment_id>_pre_registration.md` BEFORE first SFT eval

### Phase 2 exit criteria (revised)

Timeline: TBD — driven by quality gates, not calendar. Target realistic completion: **September-October 2026**.

Quality gates that MUST be met before Phase 2 exits:
- [ ] Eval scenario count ≥200
- [ ] Eval stratified into tiers (in-distribution / compositional / OOD / adversarial), scores reported separately
- [ ] All aggregate metrics reported with 95% CI
- [ ] Pre-registered failure criterion documented before fine-tune eval
- [ ] Output adapter test suite green
- [ ] METHODOLOGY §11 audit passed
- [ ] Model checkpoint registered in `models/models.json` with all required fields
- [ ] BENCHMARKING.md published with:
  - Framing A results (fine-tune vs its own base) with CI
  - Framing D results (transfer-learning ceiling characterization)
  - Failure-mode profile analysis by tier
- [ ] Author-split discipline documented and observed throughout

**Explicitly NOT required for Phase 2 exit:**
- Fine-tune beating gpt-4o-mini baseline (this is not the research claim per METHODOLOGY §1)
- Fine-tune beating baseline on any specific metric
- Any specific numeric quality threshold

The research contribution is the honest characterization. Numbers land where they land.

---

## Phase 3 — Version comparison + eval logging (post-Phase 2 exit, ~Oct-Nov 2026)

**Primary goal:** version comparison across model iterations + evaluation logging infrastructure. Ronin's confirmation (2026-07-28): "most of that phase is version comparison and evaluation logging."

**Secondary goals:** targeted expansion (multi-turn if scenarios grow to require it; recovery improvements driven by v1 failure taxonomy).

### Ronin (primary — version comparison + eval logging)
- **Ablation study**: which components earn their keep — data mix (xLAM only vs xLAM + supplementary), LoRA rank, quantization, adapter design decisions. Write-up in `docs/ablations.md`.
- **Second model variant** (if compute permits): Qwen 3B or Qwen 2.5-Coder-7B via MLX quantization, compared against 1.5B baseline. Same eval, same tiers.
- **v2, v3, ... model iterations** as ablation results indicate. Each iteration registers in `models/models.json`, results archived in `results/`.
- **Failure taxonomy** from eval runs — categorized failures across tiers, drives Marv's recovery work.
- **LLM-as-judge scoring implementation** (ADR 0008 → code) for ambiguous scenarios where deterministic scoring is insufficient.
- **Eval logging improvements**: per-run diff reports, trend tracking across model versions, regression detection.

### Marv (secondary — driven by Ronin's findings)
- **Recovery from tool failure** (Notion 5xx, calendar conflict, adapter timeout) — prioritized by Ronin's failure taxonomy
- **Multi-turn dialog state** (memory across turns within a session) — only if scenarios require it
- **SQLite state store** implementation (un-defer per DEFERRED.md trigger if scenarios require cross-request state)
- **Telemetry improvements**: aggregation, filtering, possibly simple UI or Grafana; primarily driven by eval-analysis needs
- **Cancellation + barge-in** (optional stretch)
- **Security review** across the system when real adapters approach (auth, redaction, PII handling)

### Phase 3 exit criteria

- Ablation study complete and written up in `docs/ablations.md`
- ≥2 model versions compared with statistical significance across tiers
- Failure taxonomy documented, categorized by (tool, tier, error type)
- Eval logging infrastructure supports version-diff and trend reporting
- LLM-as-judge scoring functional (or explicitly deferred to v3 with rationale)
- v2 demo video (8 min) covering the version-comparison story
- METHODOLOGY §11 audit passed for expanded eval work

---

## Phase 4 — Polish + writeup + outreach (~Nov-Dec 2026)

**Goal:** portfolio-ready. Master's applications submit Jan-Mar 2027 → need Nov 2026 first draft, Dec 2026 polished.

**Writeup discipline (locked 2026-07-12, still applies):** iterative, not one-shot. Weekly updates from Phase 3 exit through Phase 4 and into BSc final year.

Both:
- **Writeup v0** — first draft of blog post (~2500 words, technical with diagrams) covering v2 state
- **Weekly updates** — one focused update per week (new result, refined framing, new experiment) through end of Phase 4 and into BSc final year
- Demo video re-recorded with polish
- README rewritten as portfolio artifact
- CV bullets drafted per Tadashi CV Segment 2 format
- Outreach: each partner sends 5 high-quality reaches per week per Tadashi CV playbook

### Phase 4 exit criteria

- Repo publicly demoable to a senior engineer with zero hand-holding
- Both CVs updated with BAYMAX bullets
- ≥20 outreach contacts made per partner
- Master's application materials ready (blog post → portfolio link → CV)
- Decision committed: continue BAYMAX (v3 stretch) or freeze and shift to TADASHI-1

---

## Risks and mitigations (revised 2026-07-28)

| Risk | Mitigation |
|---|---|
| Scope creep ("let's add agent X") | OWNERSHIP + ROADMAP + DEFERRED docs. Any scope change requires a PR amending both, with the deferred scope moved to `future_work/`. |
| ~~Fine-tuning underperforms baseline~~ | ~~Pivot to ensemble baseline + small model~~ — **This is now the EXPECTED outcome per METHODOLOGY §1. Not a risk to mitigate; the characterization IS the contribution.** |
| Eval methodology weakness produces unreliable numbers | METHODOLOGY §11 audit BEFORE Phase 2 exit; statistical CI mandatory; tiered reporting mandatory |
| Author-split discipline slips (Marv sees eval / Ronin designs adapter) | Codified in METHODOLOGY §3; documented in RONIN_SYNC A2; mutual enforcement |
| Extended timeline pushes into Master's application window | Nov-Dec 2026 hard target; Master's applications submit Jan-Mar 2027 |
| Tool API changes mid-project (real adapters, v3+) | Tool adapter contracts versioned independently of agent core |
| One partner falls behind | Weekly sync (Mon 30 min). If behind by ≥3 days on a milestone, re-scope at the sync, don't paper over. |
| Burnout (extended timeline) | One full day off per week, mandatory. Pace over speed. |
| TADASHI-1 pulls attention prematurely | Does not start until BAYMAX Phase 2 ships. Period. |
| xLAM dataset gaps (no refusal/clarification patterns) | Supplementary template-generated training set, narrowly scoped (~100-200 examples). Ronin's 15-min pre-task on xLAM samples resolves this. |

---

## What this roadmap is not

- Not a schedule for a manager to track. There is no manager. The two of you enforce it on each other.
- Not a contract with future-you. Quarterly re-plan based on what you learn.
- Not exhaustive. Many tactical decisions happen weekly inside the phases.

## Cadence (revised for extended timeline)

- **Mon 09:00**: 30 min sync (last week, this week, blockers)
- **Wed 09:00**: 15 min standup (status only)
- **Fri afternoon**: PR review backlog cleared, week's metrics published to `results/`
- **Sat**: optional. **Sun**: hard day off.

## Parallel commitments (transparency)

So the partner knows what else is in the time budget — and can flag if BAYMAX milestones slip because of it.

**Marv:**
- ML foundations self-study to prep for SCCM6230 (Jan 2027): ~30 hours total. Tracked in a local-only plan.
- Lancaster Year 3 modules starting September 2026 — reduces weekly BAYMAX capacity.
- TADASHI-1 (individual robotics flagship): does NOT start until after BAYMAX Phase 2 ships.

**Ronin:**
- (add own parallel commitments here so Marv has the same visibility)

---

## References

- [METHODOLOGY.md](METHODOLOGY.md) — research methodology policy (governing document)
- [PROBLEM.md](PROBLEM.md) — problem statement
- [OWNERSHIP.md](OWNERSHIP.md) — contributor ownership split
- [ARCHITECTURE.md](ARCHITECTURE.md) — system architecture
- [BENCHMARKING.md](BENCHMARKING.md) — result presentation standards
- [DEFERRED.md](DEFERRED.md) — deferred features with revisit triggers
- [RONIN_SYNC.txt](../RONIN_SYNC.txt) — current meeting agenda
- [docs/decisions/](decisions/) — ADRs
- [personal/training_data_and_eval_playbook.md](personal/training_data_and_eval_playbook.md) — Marv's private working reference
