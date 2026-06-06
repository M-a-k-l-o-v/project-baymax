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

The first baseline output target is:

```text
results/v1-baseline.json
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
