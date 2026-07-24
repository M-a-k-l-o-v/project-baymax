# BAYMAX

A locally-hostable personal-task agent, evaluated on a reproducible benchmark of scripted productivity scenarios. Built to AI Systems flagship standards: train + eval + deploy pipeline, real metrics, and defensible engineering decisions.

**Status:** Phase 1 eval baseline closeout. The v1 harness has 50 scenarios, fake adapters, deterministic scoring, scripted baseline output, and an OpenAI agent baseline output.

See [docs/ROADMAP.md](docs/ROADMAP.md) for the full phase plan.

---

## What This Is

A single-process personal-task agent that:

1. Accepts text input describing a productivity task.
2. Selects and executes tool calls against Notion, Google Calendar, Gmail, and the system clipboard.
3. Confirms, refuses, or requests clarification when needed.
4. Logs actions with trace/task identifiers.

The defining property of the project is the eval suite, not the agent itself. BAYMAX measures task success, tool-call accuracy, argument accuracy, clarification/refusal accuracy, hallucination rate, latency, and cost per task.

## What This Is Not

- Not a general personal assistant.
- Not a multi-agent orchestration framework.
- Not a thin wrapper around a hosted model.
- Not benchmarked only against itself.

For the full anti-claims list and research question, see [docs/PROBLEM.md](docs/PROBLEM.md).

---

## Team

| Name | Role | Owned modules |
|---|---|---|
| Marv | Person 1 | Agent core, inference service, telemetry |
| Ronin | Person 2 | Eval harness, training pipeline, tool adapters |

Authoritative ownership rules and PR review protocol: [docs/OWNERSHIP.md](docs/OWNERSHIP.md).

---

## Documentation

| Doc | Purpose |
|---|---|
| [docs/PROBLEM.md](docs/PROBLEM.md) | What BAYMAX is building and why |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design and ownership boundaries |
| [docs/OWNERSHIP.md](docs/OWNERSHIP.md) | Module ownership, PR rules, conflict resolution |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Phase plan and milestones |
| [docs/BENCHMARKING.md](docs/BENCHMARKING.md) | Eval methodology, commands, and Phase 1 results |
| [docs/SCORING.md](docs/SCORING.md) | Deterministic scoring rules and failure reasons |
| [docs/decisions/](docs/decisions/) | Architecture Decision Records |
| [future_work/](future_work/) | Parked scope ideas |

---

## Quick Start

Install dependencies:

```powershell
uv sync --frozen --all-groups
```

Run checks:

```powershell
uv run ruff format --check
uv run ruff check .
uv run pyright
uv run pytest
```

Run the scripted baseline:

```powershell
python -m baymax.eval.cli run-scripted `
  --scenarios scenarios\v1 `
  --responses scenarios\v1\scripted_responses\v1-scripted.json `
  --output results\v1-baseline.json
```

Run the OpenAI agent baseline:

```powershell
$env:OPENAI_API_KEY="your_api_key"
python -m baymax.eval.cli run-agent-openai `
  --scenarios scenarios\v1 `
  --output results\v1-agent-openai.json `
  --model gpt-4o-mini
```

Phase 1 result files are committed under `results/`.

---

## Phase 1 Outputs

| File | Purpose |
|---|---|
| [results/v1-baseline.json](results/v1-baseline.json) | Deterministic scripted baseline over 50 scenarios |
| [results/v1-agent-openai.json](results/v1-agent-openai.json) | OpenAI agent baseline over the same 50 scenarios |

The OpenAI baseline currently reaches `0.52` task success. Its main failure mode is acting when it should clarify, refuse, or wait for confirmation.

---

## License

[MIT](LICENSE) - Marv and Ronin, 2026.
