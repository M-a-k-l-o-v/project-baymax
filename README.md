# BAYMAX

A locally-runnable personal-task agent with an eval harness. Stepping-stone learning project — shipped as portfolio evidence of engineering + methodology discipline, not as a daily-driver assistant or research contribution.

**Status**: Phase 1 eval baseline shipped (50 scenarios, OpenAI + scripted baselines). Phase 2 in progress (MLX backend, LoRA fine-tune, output adapter). Target ship: end of September 2026.

See [docs/PROJECT.md](docs/PROJECT.md) for the full "what BAYMAX is and isn't."

---

## What it does

1. Accepts text input describing a productivity task
2. Selects and executes tool calls against **fake** in-memory adapters (calendar / notion / gmail / clipboard)
3. Confirms, refuses, or requests clarification
4. Logs actions with trace / task identifiers
5. Runs against a scripted eval suite; produces metrics JSON

## What it doesn't do (honest scope)

- **No real API integration** — fake adapters only. Not connected to your real Google Calendar / Gmail / Notion.
- **Not a daily-driver assistant** — response quality too low to trust for real actions
- **No menu bar app / voice / chat UI** — REST endpoint only (`POST /invoke`)
- **No context memory across requests** — each request stateless
- **No streaming, no multi-turn dialog**

Full list in [docs/DEFERRED.md](docs/DEFERRED.md).

---

## Team

| Name | Owned modules |
|---|---|
| **Marv** | Agent core, inference service, backends (OpenAI + MLX), output adapter, telemetry |
| **Ronin** | Eval harness, training pipeline, tool adapters (fake), scenario authorship |

Full ownership rules: [docs/OWNERSHIP.md](docs/OWNERSHIP.md).

---

## Documentation

| Doc | Purpose |
|---|---|
| [docs/PROJECT.md](docs/PROJECT.md) | What BAYMAX is (and isn't) — the framing doc |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design |
| [docs/OWNERSHIP.md](docs/OWNERSHIP.md) | Module ownership + PR rules |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Timeline to ship (~5 weeks from 2026-08-24) |
| [docs/BACKEND_FLOW.md](docs/BACKEND_FLOW.md) | Backend + agent design diagrams |
| [docs/BENCHMARKING.md](docs/BENCHMARKING.md) | Eval methodology + results |
| [docs/SCORING.md](docs/SCORING.md) | Deterministic scoring rules |
| [docs/DEFERRED.md](docs/DEFERRED.md) | Known limitations + not-implemented items |
| [docs/decisions/](docs/decisions/) | ADR archive |

---

## Quick start

Install dependencies:

```bash
uv sync --frozen --all-groups
```

Run checks:

```bash
uv run ruff format --check
uv run ruff check .
uv run pyright
uv run pytest
```

Run the scripted baseline:

```bash
python -m baymax.eval.cli run-scripted \
  --scenarios scenarios/v1 \
  --responses scenarios/v1/scripted_responses/v1-scripted.json \
  --output results/v1-baseline.json
```

Run the OpenAI agent baseline:

```bash
export OPENAI_API_KEY="your_api_key"
python -m baymax.eval.cli run-agent-openai \
  --scenarios scenarios/v1 \
  --output results/v1-agent-openai.json \
  --model gpt-4o-mini
```

Phase 1 result files are committed under `results/`.

---

## Current results (Phase 1 baselines)

| Backend | task_success_rate | scenarios |
|---|---|---|
| Scripted baseline | see `results/v1-baseline.json` | 50 |
| gpt-4o-mini | **0.52** | 50 |
| Qwen 1.5B + LoRA (smoke test) | 0.24 | 50 |

Phase 2 will add: proper Qwen training runs (not smoke test), MLX backend integration, output adapter, expanded eval to ~200 scenarios. Fine-tune is EXPECTED to underperform baseline — honest characterization of transfer ceiling, not a project failure.

---

## License

[MIT](LICENSE) — Marv and Ronin, 2026.
