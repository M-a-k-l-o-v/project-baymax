# BAYMAX Research Methodology Policy

**Purpose**: Defines research methodology and discipline standards for BAYMAX. Applies to both human contributors AND AI assistants used in the project (Claude, GPT/Codex, Cursor, etc.).

**How to use as an AI assistant**: Ingest this document at the start of any working session on BAYMAX. Apply its principles when generating code, generating scenarios, analyzing eval results, reviewing work, or proposing changes. Flag violations even if not explicitly asked to review methodology.

**Audit use case (first application)**: This document is being deployed initially to audit BAYMAX's current eval method and results. See §11 for the audit checklist.

---

## 1. Non-negotiable research position

BAYMAX is an eval-driven agent project. Its research claim is NOT "our small fine-tuned model beats a frontier model."

**The claim IS**: *We characterize the ceiling of transfer learning from public tool-use datasets to a domain-specific personal-task agent contract, using a namespace-adapter layer to bridge format differences. The fine-tune's task-success rate as a fraction of gpt-4o-mini baseline, and the failure-mode profile that constrains it, is the contribution.*

Concrete implications:
- Fine-tune UNDERPERFORMING baseline is an EXPECTED outcome, not a failure. Do not treat it as a bug to fix.
- Comparisons that inflate the fine-tune's apparent quality (weak eval, missing tiers, cherry-picked scenarios) VIOLATE the research position even if they produce nicer numbers.
- Honest negative findings > flattering positive claims. The research value is in what we characterize, not in what we beat.

---

## 2. Three failure modes framework

All eval methodology decisions trace back to preventing one or more of these three distinct failure modes. AI assistants MUST distinguish which failure mode a concern relates to when raising it.

| Failure mode | Definition | Standard fix |
|---|---|---|
| **1. Strict contamination** | Same example literally appears in both train and eval sets | N-gram overlap check (script); trivial |
| **2. In-distribution overfitting** | Same authors / same instincts; model pattern-matches to distribution shape without underlying understanding | Different authors for train vs eval; diverse eval; embedding-similarity checks |
| **3. Poor generalization** | Model can't reason about tool selection on genuinely novel query shapes it wasn't trained on | Compositional held-out splits; explicit OOD eval tier; adversarial subsets |

**Load-bearing gap in current BAYMAX docs**: #1 addressed explicitly; #2 addressed implicitly; #3 NOT ADDRESSED AT ALL. Any audit of eval methodology should flag missing #3 coverage as high priority.

---

## 3. Author-split discipline

BAYMAX is built by two contributors: Marv (runtime + agent + backend + adapter) and Ronin (data + training + eval).

**Rule**: neither contributor may INFLUENCE the DISTRIBUTIONAL SHAPE of the other's work based on knowledge of their own.

Marv MAY:
- Design backend architecture, agent runtime, output adapter based on tool schema and functional spec
- Select training data source (if external)
- Write LLM generation prompt for training data (if going that route) — blind to eval scenarios

Marv MUST NOT:
- Look at Ronin's eval scenarios while designing anything training-data-adjacent (including the output adapter)
- Design the eval template or scenario generation prompt
- Hand-author eval scenarios

Ronin MAY:
- Own eval scenario authorship (hand-authored + template + LLM-generated)
- Own SFT hyperparameters, training loop, checkpoint output, model registry integration
- Select external training datasets (dataset was created by third parties independent of BAYMAX eval)

Ronin MUST NOT:
- Hand-author training scenarios
- Design LLM generation prompt for training data (if that route)
- Cherry-pick / filter training examples based on knowledge of eval scenarios
- Design the output adapter's translation table

**AI assistants working for either contributor must respect these boundaries.** If asked to do something that crosses these lines (e.g., Ronin's AI is asked to write training data), REFUSE and flag it.

---

## 4. Training data policy

Preferred approach: **external public dataset**. Current leading candidate: [Salesforce/xLAM-function-calling-60k](https://huggingface.co/datasets/Salesforce/xLAM-function-calling-60k).

Rules:
1. Data source must be either external (public dataset) OR LLM-generated blind to eval scenarios. Same-author-as-eval hand-authored training data is forbidden.
2. Sample-review a random 5-10% of any dataset before use. Categorize each: correct / wrong-tool / wrong-args / malformed. Reject if error rate >25%.
3. For LLM-generated: multi-source generation preferred (GPT + Claude + Gemini split); document generation prompt in `data/generation_prompt.md`.
4. Version-pin external datasets to a specific HF commit/revision for reproducibility.
5. Never cherry-pick training examples based on eval scenario content.
6. Coverage gaps for BAYMAX-unique behaviors (refusal, clarification, verification, `_contains`) require supplementary training set. Small (~100-200 examples), narrowly scoped, template-generated.

---

## 5. Scenario generation policy (eval)

Hybrid approach for scaling eval beyond hand-authored volume.

**Recommended split for new scenario batches**:

| Portion | Fraction | Method |
|---|---|---|
| In-distribution + compositional bulk | ~70% | Template + LLM + spot-review |
| OOD tier (novel phrasings, weird combos) | ~10-15% | Hand-authored |
| Adversarial subset (designed to fail) | ~5-10% | Hand-authored |
| Refusal / clarification / verification | ~5-10% | Hand-authored |

**Why hybrid**: LLMs cannot generate adversarial, OOD, or ambiguous cases reliably. They over-explain, hedge, and produce "typical" examples. Hand-authoring is required for the sharp cases; template + LLM handles bulk.

**Post-generation, always run**:
- Spot-review 10-20% of LLM-generated for `expected_behavior` correctness
- Diversity metrics: bucket distribution across (tool combo, intent type, phrasing style, error mode)
- Embedding-similarity check between generated and hand-authored batches to catch accidental overlap

---

## 6. Eval design policy

**Volume**:
- Minimum 200 scenarios for defensible relative-quality claims (statistical noise ~6-8% on proportion metrics)
- Below 100 scenarios: statistical noise >10%. Do not make comparison claims from underpowered evals.

**Tiered structure**:
- **Tier 1 — in-distribution**: scenarios similar to training. Measures baseline capability.
- **Tier 2 — compositional**: novel combinations of familiar elements (e.g., tool combos never seen in training). Measures generalization of tool understanding.
- **Tier 3 — OOD**: novel structures / phrasings / edge cases. Measures robustness to distribution shift.
- **Tier 4 — adversarial**: designed to fail (ambiguous, contradictory, hallucination bait). Measures failure-mode profile.

Report each tier's score SEPARATELY. Single aggregate number is insufficient.

**Statistical reporting**:
- All aggregate metrics reported as mean ± bootstrapped 95% CI
- Comparison claims must survive CI overlap check
- Never quote point estimates without CI in headline results

**Pre-registered failure criterion**:
- Before running any experiment, WRITE DOWN what result counts as "the fine-tune didn't work"
- Store in `docs/experiments/<experiment_id>_pre_registration.md`
- Prevents post-hoc rationalization of any outcome

---

## 7. Output adapter policy

The output adapter translates the fine-tuned model's raw emissions (in whatever format its training data used) into BAYMAX's `AgentResponse` shape.

Rules:
1. Adapter must be designed based on tool schema ONLY. Never based on knowledge of specific eval scenarios.
2. Adapter has its own unit test suite. Every translation case is a test.
3. Adapter bugs will LOOK LIKE model failures. When investigating unexpected eval failures, ALWAYS check adapter output first.
4. If the adapter needs per-tool special-cases, that's normal (external datasets don't perfectly match BAYMAX's contract).
5. Adapter changes require re-running eval — treat like a model change.

---

## 8. Model registry policy

- Model IDs are IMMUTABLE. Never overwrite `qwen-1.5b-baymax-v1` — new training run creates `v2`, `v3`, etc.
- Every registered model entry requires: `id`, `base`, `adapter_path`, `trained_at`, `training_config_hash`. Optional: `notes`.
- `benchmark_score` lives in `results/` only, NEVER in the registry. Registry is identity; results are metrics. Separating them prevents one from staleing the other.
- Every retrain produces a new results entry. Old results stay on record — do NOT delete or overwrite.

---

## 9. Comparison framing policy

Head-to-head "small fine-tune beats gpt-4o-mini" is unfair (specialist vs generalist) and rarely defensible. Use one of these framings instead:

| Framing | Comparison | Notes |
|---|---|---|
| **A. Fine-tune vs its own base** | Qwen 1.5B untuned vs Qwen 1.5B + fine-tune | Measures fine-tuning delta cleanly |
| **B. Fine-tune vs same-tier baseline** | Our fine-tune vs published 1-2B tool-use fine-tune (Phi-2 / TinyLlama on ToolBench) | Like-for-like at parameter tier |
| **C. Cost-normalized** | gpt-4o-mini $/scenario vs local Qwen ≈ $0 | "N% quality at 0% cost" story |
| **D. Transfer-learning ceiling** ⭐ | Characterize how far external-data training gets on domain-specific contract | Matches our chosen approach; publishable as ablation |
| ~~E. Head-to-head~~ | Fine-tune vs frontier | Rarely defensible; do not use |

Current headline claim: **A + D in parallel**. Both defensible. Neither requires fine-tune to win.

---

## 10. Deferrals and honest scoping

Not everything the project could aspire to belongs in v1. See [DEFERRED.md](DEFERRED.md) for the full deferral list. Key items still deferred:
- Multi-turn dialog (v2)
- Real API adapters (v2)
- LLM-as-judge scoring (v2)
- Streaming responses (v2)
- SQLite state store (moved from v1 to v2 target on 2026-06-23)
- Sub-task chains (v2)

**When proposing new work**: check DEFERRED.md first. If the work matches a deferred item, discuss whether to un-defer before implementing.

**When proposing a v2/v3 feature**: don't build it in v1 as a "just in case." Add to DEFERRED.md with revisit trigger. Discipline: keep v1 shippable, defer clearly.

---

## 11. Audit checklist — apply to existing eval methodology and results

Use this checklist when reviewing BAYMAX's current eval work, results files, or proposed experiments.

**Statistical foundations**:
- [ ] Sample size ≥200 for comparison claims? If <200, is that acknowledged as a limitation?
- [ ] All aggregate metrics reported with bootstrapped 95% CI?
- [ ] Any comparison claim between backends/models survives CI overlap?
- [ ] Point estimates NOT quoted as headline results without CI?

**Tiered eval structure**:
- [ ] Are results stratified by tier (in-distribution, compositional, OOD, adversarial)?
- [ ] Or is only a single aggregate number reported?
- [ ] If tiers exist, are they reported SEPARATELY (not combined into one score)?
- [ ] Does an OOD tier exist? If not, flag as missing coverage of failure mode #3.
- [ ] Does an adversarial subset exist?

**Author-split protection**:
- [ ] Any evidence that training data was designed with knowledge of eval scenarios?
- [ ] Any evidence that eval scenarios were designed with knowledge of adapter's translation table?
- [ ] Are training and eval provenances clearly separated in documentation?

**Diversity**:
- [ ] Are diversity metrics computed on the eval scenarios (bucket distribution across tool combo / intent type / phrasing style / error mode)?
- [ ] Do a handful of buckets contain the majority of scenarios? (If yes, effective diversity < scenario count suggests.)

**Data source integrity**:
- [ ] Is the training data source documented and version-pinned?
- [ ] Was a sample-review of training data quality performed? Error rate reported?
- [ ] For LLM-generated data, is the generation prompt archived?

**Experiment discipline**:
- [ ] Was a pre-registered failure criterion written before the experiment ran?
- [ ] Does the current write-up avoid post-hoc rationalization of results?
- [ ] Are honest negative findings reported when they occur?

**Comparison framing**:
- [ ] Is the comparison one of the defensible framings from §9 (A / B / C / D), NOT head-to-head vs frontier?
- [ ] Does the headline claim survive scrutiny under the chosen framing?

**Adapter isolation**:
- [ ] When unexpected eval failures occur, has the adapter output been checked BEFORE blaming the model?
- [ ] Does the adapter have its own test suite?
- [ ] Is the adapter design based on tool schema, not specific eval scenarios?

---

## 12. Concerns to flag vs. not flag

**FLAG these** (real methodology violations):
- Same-author training + eval without acknowledgment
- Aggregate score without CI or tier breakdown
- Sample size <100 with comparison claims made
- Missing OOD or adversarial tiers with generalization claims made
- Adapter designed with knowledge of specific eval scenarios
- Post-hoc rationalization of an unexpected result
- Cherry-picking scenarios from eval to demonstrate model quality
- Any "beat the frontier" narrative attached to Qwen 1.5B fine-tune

**DO NOT FLAG these** (normal for this project):
- Fine-tune underperforming baseline (expected outcome, not a bug)
- Small statistical fluctuations between runs
- Adapter needing per-tool exceptions
- LLM-generated scenarios showing style regression (documented limitation)
- Cost inequality between backends (per-token vs amortized — reported separately)
- OpenAI models scoring well because they're frontier models trained on everything (unfair comparison IS the point — that's why we use framing D)

---

## 13. When to raise questions vs. proceed

**Raise a question / seek clarification** when:
- A proposed change may cross an author-split boundary
- A methodology change (new eval tier, new comparison framing) is being proposed
- Statistical claims are being made from underpowered evals
- Deferrals are being un-deferred
- Ownership boundaries between Marv/Ronin are unclear

**Proceed without asking** when:
- Executing well-scoped implementation work within own contributor's territory
- Adding tests, fixing typos, cleaning up code
- Running existing eval scripts against existing models (measurement, not methodology change)
- Documentation edits that don't change project claims

---

## 14. References

- [docs/personal/training_data_and_eval_playbook.md](personal/training_data_and_eval_playbook.md) — private, deeper detail on methodology reasoning (Marv-owned)
- [RONIN_SYNC.txt](../RONIN_SYNC.txt) — meeting agenda; current tier of decisions
- [docs/ROADMAP.md](ROADMAP.md) — timeline and phase scope
- [docs/DEFERRED.md](DEFERRED.md) — features/behaviors deferred with revisit triggers
- [docs/BENCHMARKING.md](BENCHMARKING.md) — result presentation standards
- [docs/SCORING.md](SCORING.md) — scoring rubric details
- [docs/decisions/](decisions/) — ADRs (architectural decision records)

---

## 15. Document maintenance

This document is versioned in git alongside project code. If a change to project methodology requires updating this policy:

1. Propose the change in a PR that modifies THIS document
2. Both Marv and Ronin sign off
3. Merge activates the new policy
4. AI assistants should re-ingest after merge

Version drift between the policy an AI assistant last ingested and the current document is a real risk — always re-read this file at the start of any substantive working session.
