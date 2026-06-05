# BAYMAX

A locally-hostable personal-task agent, evaluated on a reproducible benchmark of scripted productivity scenarios. Built to AI Systems flagship standards — train + eval + deploy pipeline, real metrics, defensible under interview questioning.

**Status:** pre-Phase 0 (week of 2026-05-18). Repo is being restructured from its prior multi-prototype form. See [docs/ROADMAP.md](docs/ROADMAP.md) for phase plan.

---

## What this is

A single-process agent that:

1. Accepts voice or text input describing a productivity task
2. Selects and executes a sequence of tool calls against Notion, Google Calendar, Gmail, and the system clipboard
3. Confirms or requests clarification
4. Logs every action with a trace ID

The defining property of the project is the **eval suite**, not the agent itself: ≥100 scripted scenarios with measured task success rate, tool-call accuracy, hallucination rate, latency P50/P99, and cost per task. Every claim is reproducible from the repo.

## What this is not

- Not a "general personal assistant"
- Not a multi-agent orchestration framework
- Not a thin wrapper around GPT-4 — the v1 deliverable includes a fine-tuned local model deployed via MLX
- Not benchmarked only against itself

For the full anti-claims list and the research question this project answers, see [docs/PROBLEM.md](docs/PROBLEM.md).

---

## Team

| Name | Role | Owned modules |
|---|---|---|
| Marv | Person 1 | Agent core · Inference service · Telemetry |
| Ronin | Person 2 | Eval harness · Training pipeline · Tool adapters |

Authoritative ownership rules and PR review protocol: [docs/OWNERSHIP.md](docs/OWNERSHIP.md).

---

## Documentation

| Doc | Purpose |
|---|---|
| [docs/PROBLEM.md](docs/PROBLEM.md) | What we're building and why; v1/v2 done criteria |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design (scaffold with TODO blocks — owners fill in) |
| [docs/OWNERSHIP.md](docs/OWNERSHIP.md) | Module ownership, PR rules, conflict resolution |
| [docs/ROADMAP.md](docs/ROADMAP.md) | 4-phase plan, 19 weeks, weekly milestones |
| [docs/decisions/](docs/decisions/) | ADRs (Architecture Decision Records) — one per significant choice |
| [docs/BENCHMARKING.md](docs/BENCHMARKING.md) | Eval methodology and result tables (added in Phase 1) |
| [future_work/](future_work/) | Briefs for re-scopings considered and parked (Options β and γ) |

---

## Target repo layout

This is the structure being established in Phase 0. The current state on disk differs — see ROADMAP Phase 0 for the migration plan.

```
BAYMAX/
├── README.md                    ← this file
├── pyproject.toml               ← single dependency manifest
├── .env.example
├── .github/workflows/           ← lint + typecheck + test on every PR
├── docs/
│   ├── PROBLEM.md
│   ├── ARCHITECTURE.md
│   ├── OWNERSHIP.md
│   ├── ROADMAP.md
│   ├── BENCHMARKING.md
│   ├── decisions/               ← ADRs
│   └── diagrams/
├── src/
│   └── baymax/
│       ├── core/                ← agent loop, tool-call contract, state machine  (Marv)
│       ├── service/             ← FastAPI, inference backend abstraction          (Marv)
│       ├── telemetry/           ← logging, traces, cost tracker                   (Marv)
│       ├── eval/                ← scenarios, runner, metrics, judge protocol     (Ronin)
│       ├── models/              ← data prep, SFT/LoRA, model registry             (Ronin)
│       └── tools/               ← Notion, Gmail, Calendar, clipboard adapters    (Ronin)
├── scenarios/
│   ├── v1/                      ← 50 scripted scenarios for v1
│   └── v2/                      ← +150 for v2
├── experiments/                 ← training runs, config snapshots
├── results/                     ← versioned eval result JSONs
├── tests/
│   ├── unit/
│   └── integration/
├── scripts/
│   └── run_benchmarks.sh
└── future_work/                 ← parked re-scopings (β, γ)
```

---

## Quick start

> Not yet runnable end-to-end. Phase 0 (week of 2026-05-18) establishes the scaffolding. Phase 1 (May 25 – Jun 21) produces the first end-to-end baseline.

Local setup that works today:

```bash
# 1. Install uv (one time)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Sync deps and install the package in dev mode
uv sync

# 3. Copy the env template and fill in your own credentials
cp .env.example .env
# (edit .env — see comments in .env.example for what each variable means)

# 4. Run the development checks
uv run ruff check
uv run pyright
uv run pytest
```

When Phase 1 is complete, this section will also document:

- How to run the eval harness against a baseline
- How to run a single scenario end-to-end

---

## Why this exists

Two students breaking into AI engineering need a flagship project that signals real engineering depth, not breadth. This project is sized and scoped to be defensible under senior-engineer questioning: every metric is reproducible, every module has clear ownership, every decision has an ADR. The discipline matters more than the surface area.

The full strategic rationale lives outside the repo. The non-negotiable rules that shape this project:

1. No fake metrics
2. No vague AI branding
3. No weak features taking space from stronger ones
4. No "I built this" for code the human cannot defend line-by-line
5. AI as leverage, not substitution — humans own architecture, core algorithms, and debugging

---

## License

[MIT](LICENSE) — Marv and Ronin, 2026.