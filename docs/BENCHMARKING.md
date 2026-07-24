# Benchmarking

This document defines how BAYMAX evaluation scenarios are written, scored, and reported.

Phase 1 starts with scripted scenarios and fake tool adapters so the evaluation harness is reproducible before any real APIs are introduced. The goal is to measure agent behaviour in a controlled environment before connecting BAYMAX to live Notion, Google Calendar, Gmail, or clipboard integrations.

## Scenario Difficulty Labels

Each scenario must include one difficulty label:

* `explicit`: The user gives exact date, time, or task details directly.
* `implicit`: The user uses relative or natural phrasing that must be resolved using `current_time`, such as "tomorrow", "next Friday", or "in two hours".
* `contextual`: The agent must inspect `initial_state` to identify the correct entity or action.
* `ambiguous`: The agent should ask a clarification question instead of taking action.
* `multi_step`: The agent must call more than one tool to complete the task.

## Scenario Files

Scenario fixtures live under `scenarios/v1/`.

Each scenario must validate against:

```text
src/baymax/eval/schemas/scenario.schema.json
```

Each scenario includes `current_time` so relative phrases like "tomorrow", "Friday", or "in two hours" resolve deterministically during eval runs.

Each scenario defines:

* the user input
* the current time
* the available tools
* the initial fake tool state
* the expected behaviour
* the success criteria

## Phase 1 Metrics

The Phase 1 runner will report the following metrics:

### Task Success

Whether the scenario reached the expected final outcome.

### Tool-Call Accuracy

Whether the agent selected the correct tool for the scenario.

### Argument Accuracy

Whether the agent supplied correct tool arguments, such as date, time, title, recipient, or duration.

### Clarification Accuracy

For ambiguous scenarios, whether the agent asked for the required missing information instead of guessing or taking premature action.

### Hallucination Rate

How often the agent invents unsupported actions, calls unavailable tools, claims success without tool execution, or fabricates state not present in the scenario.

### Latency

The elapsed time for the scenario run, reported at minimum as total latency per scenario. Later runs may include P50 and P99 latency.

### Cost

The estimated model/API cost per scenario and per benchmark run.

## Phase 1 Output

The first scripted baseline output target is:

```text
results/v1-baseline.json
```

The first OpenAI agent baseline output target is:

```text
results/v1-agent-openai.json
```

This file should include:

* run ID
* model/backend name
* scenario count
* aggregate metrics
* per-scenario pass/fail results
* failure reasons where applicable
* timestamp
* benchmark configuration

## Phase 1 Commands

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

Run local verification:

```powershell
uv run ruff format --check
uv run ruff check .
uv run pyright
uv run pytest
```

## Phase 1 Baseline Results

The scripted baseline is expected to pass all 50 scenarios because it uses
hand-authored responses that match the scenario fixtures.

The first OpenAI agent baseline was run against the same 50 scenarios:

```text
backend: openai:gpt-4o-mini
scenario_count: 50
task_success_rate: 0.52
average_tool_call_accuracy: 0.82
average_argument_accuracy: 0.9083333333333333
average_clarification_accuracy: 0.5555555555555556
average_refusal_accuracy: 0.21428571428571427
average_hallucination_rate: 0.0
average_latency_ms: 2518.9
total_cost_usd: 0.0058130000000000005
```

The main baseline weakness is boundary judgment: the general agent often takes
action when the expected behavior is to clarify, refuse, or wait for
confirmation. That result is useful because BAYMAX's target local agent should
be trained and evaluated against these domain-specific rules, not only generic
tool-use ability.
