# Scoring

This document tracks the Phase 1 scoring rules for BAYMAX eval scenarios.

The scorer is deterministic. It compares an agent response against the expected
behavior in a scenario. The runner also executes tool calls against fake adapters
and records `tool_results` and `final_state`; LLM-as-judge scoring is deferred.

## Current Scoring Rules

### Tool-Call Accuracy

Tool-call accuracy is the number of correct ordered expected tool calls divided
by the number of expected tool calls.

For multi-step scenarios, order currently matters.

Example:

```text
expected: notion.create_task, gmail.create_draft
actual:   notion.create_task, calendar.create_event
score:    1 / 2 = 0.5
```

### Unordered Tool Match

Unordered tool match gives visibility into whether the agent selected the right
tools but used them in the wrong order.

Example:

```text
expected: notion.create_task, gmail.create_draft
actual:   gmail.create_draft, notion.create_task
ordered tool-call accuracy: 0.0
unordered tool match:       1.0
failure reason:             wrong_tool_order
```

### Hallucination Rate

The current hallucination rate only tracks unsupported tool calls:

```text
hallucinated tool calls / total actual tool calls
```

An actual tool call is hallucinated when its tool name is not listed in the
scenario's `available_tools`.

### Task Success

Task success is true only when there are no failure reasons and argument
accuracy is `1.0`.

### Argument Accuracy

Argument accuracy is the number of correct expected argument checks divided by
the total number of expected argument checks.

Exact keys require exact matches:

```text
recipient
duration_minutes
status
start_date
start_time
```

Keys ending in `_contains` are substring checks against the corresponding actual
argument without the suffix.

Example:

```text
expected: body_contains = "added it"
actual:   body = "I added it to Notion."
result:   correct
```

For multi-step scenarios, arguments are scored by ordered expected tool call. If
an expected tool call is missing, its argument checks score `0`.

### Clarification Accuracy

Clarification accuracy applies only to scenarios whose expected behavior is
`clarification`.

- no tool should be called
- the response message should contain the required clarification keywords

The score is the number of matched required keywords divided by the number of
required keywords. If a tool is called, clarification accuracy is `0.0`.

### Refusal Accuracy

Refusal accuracy applies only to scenarios whose expected behavior is `refusal`.

- no tool should be called
- the response message should contain the required refusal keywords

The score is the number of matched required keywords divided by the number of
required keywords. If a tool is called, refusal accuracy is `0.0`.

## Current Failure Reasons

- `wrong_tool_order`: The right tools were selected but not in the expected order.
- `missing_tool_call`: The agent made fewer tool calls than expected.
- `extra_tool_call`: The agent made more tool calls than expected.
- `hallucinated_tool_call`: The agent called a tool not listed in `available_tools`.
- `wrong_tool_call`: The agent called the wrong tool for one or more expected positions.
- `missing_clarification`: The expected clarification was not asked.
- `missing_refusal`: The expected refusal was not provided.
- `premature_tool_call`: The agent called a tool when it should have clarified or refused.

## Planned Scoring Work

### Entity Grounding

Track hallucinated entities that are not grounded in user input or
`initial_state`.

Examples:

- invented email address
- invented contact
- invented calendar event
- invented Notion task

Potential future failure reason:

- `hallucinated_entity`

### State and Success Claims

Track cases where the agent claims something happened without a supporting tool
call or adapter result.

Potential future failure reasons:

- `hallucinated_state`
- `hallucinated_success`

### Deeper Adapter Outcome Scoring

Fake adapters are already executed by the runner. Future scoring should inspect
adapter outcomes more deeply.

Examples:

- permission denied
- timeout
- rate limit
- validation error
- tool execution failed

The agent must not claim success when the adapter reports failure. Future
failure reasons may distinguish validation failure, execution failure, and
hallucinated success.

## Non-Goals for the First Scorer

- no LLM-as-judge
- no semantic argument matching
- no fuzzy matching beyond explicit `*_contains` checks
- no retries or recovery scoring
- no real API execution
