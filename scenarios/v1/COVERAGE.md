# v1 Scenario Coverage

This checklist tracks scenario coverage gaps for the v1 benchmark. Mark an item
complete only when at least one committed scenario validates for that behavior.

## Calendar

- [x] Calendar contextual scenario
  - `calendar_contextual_reschedule_001`
- [x] Calendar clarification scenario
  - `calendar_clarify_time_001`
- [x] Calendar explicit scenario
  - `calendar_audio_001`
- [x] Calendar implicit scenario
  - `calendar_create_001`
- [x] Calendar audio-path scenario
  - `calendar_audio_001`

## Gmail

- [x] Gmail contextual scenario
  - `gmail_contextual_reply_001`
- [x] Gmail clarification scenario
  - `gmail_clarify_recipient_001`
- [x] Gmail explicit scenario
  - `gmail_create_draft_001`
- [ ] Gmail implicit scenario
  - Example: email someone "tomorrow's plan" using relative time wording.
- [x] Gmail refusal scenario
  - `gmail_refusal_001`

## Notion

- [x] Notion contextual scenario
  - `notion_contextual_complete_001`
- [ ] Notion clarification scenario
  - Example: user asks to update "the task" when multiple tasks match.
- [x] Notion explicit scenario
  - `notion_explicit_create_001`
- [x] Notion implicit scenario
  - `notion_create_task_001`

## System Clipboard

- [x] System clipboard contextual scenario
  - `clipboard_task_from_copy_001`
- [ ] System clipboard clarification scenario
  - Example: copied text contains multiple possible tasks.
- [ ] System clipboard explicit scenario
  - Example: save the exact copied text as a Notion note.
- [ ] System clipboard implicit scenario
  - Example: copied text contains relative date wording that needs `current_time`.

## Cross-Tool Coverage

- [x] Multi-step scenario
  - `multi_tool_task_email_001`, `clipboard_task_from_copy_001`
- [x] Tool-unavailable scenario
  - `tool_unavailable_email_001`
- [ ] Multiple matching entities scenario
  - Example: two meetings with the same person, requiring clarification.
- [ ] Timezone-sensitive scenario
  - Example: schedule across explicit timezone wording.
- [ ] Schema/loader drift check
  - Example: tests prove committed schema and Pydantic loader stay aligned.

## State Coverage

- [x] Empty initial state scenario
  - `calendar_create_001`, `calendar_audio_001`, `notion_create_task_001`
- [x] Single matching entity scenario
  - `calendar_contextual_reschedule_001`, `notion_contextual_complete_001`
- [ ] Multiple matching entities scenario
  - Example: two meetings with the same person, requiring clarification.
- [x] No matching entity scenario
  - `calendar_no_matching_reschedule_001`
- [ ] Duplicate existing entity scenario
  - Example: user asks to create a task that already exists in `initial_state`.
- [ ] Conflicting entity scenario
  - Example: user schedules a calendar event during an existing event.

## Metric Coverage

- [x] Task success scenario
  - `calendar_create_001`, `gmail_create_draft_001`, `notion_create_task_001`
- [x] Tool-call accuracy scenario
  - `calendar_create_001`, `gmail_create_draft_001`, `notion_create_task_001`
- [x] Argument accuracy scenario
  - `calendar_create_001`, `gmail_create_draft_001`, `notion_create_task_001`
- [x] Clarification accuracy scenario
  - `gmail_clarify_recipient_001`
- [x] Hallucination-rate scenario
  - `gmail_refusal_001`
- [ ] Latency scenario
  - Example: any scenario once the runner records elapsed time.
- [ ] Cost scenario
  - Example: any scenario once the runner records model/backend cost.

## Failure-Mode Coverage

- [x] No matching entity scenario
  - `calendar_no_matching_reschedule_001`
- [ ] Tool adapter failure scenario
  - Example: fake adapter returns permission denied, timeout, or rate limit.
- [ ] Hallucinated success scenario
  - Example: tool execution fails, and the agent must not claim the action succeeded.
- [ ] Duplicate prevention scenario
  - Example: user asks to create a task that already exists in `initial_state`.
- [ ] Invalid argument scenario
  - Example: agent must not call a tool with missing, malformed, or impossible arguments.

## Operation-Type Coverage

- [ ] Delete/cancel scenario
  - Example: cancel an existing calendar event or delete a draft/task.
- [ ] Search/list scenario
  - Example: list tasks due tomorrow or find emails from a sender.
- [ ] Read-only no-mutation scenario
  - Example: user asks what events they have tomorrow, and no state should be modified.
- [ ] Draft-vs-send distinction scenario
  - Example: distinguish "draft an email" from "send an email".

## Time and Conflict Coverage

- [ ] Relative time scenario
  - Example: schedule something "in two hours" using `current_time`.
- [ ] Ambiguous time phrase scenario
  - Example: "remind me tonight" should trigger clarification if no time rule exists.
- [ ] Calendar conflict scenario
  - Example: user schedules an event during an existing event in `initial_state`.

## Safety and Scope Coverage

- [ ] Harmless out-of-scope request
  - Example: user asks BAYMAX to order food or book a taxi when no such tool exists.
- [ ] Destructive action confirmation scenario
  - Example: user asks to delete/cancel something, and the agent should ask for confirmation if that is the product rule.

## Target

Phase 1 eventually needs 50 scripted scenarios across Notion, Calendar, Gmail,
system clipboard, clarification, refusal, contextual lookup, and multi-step
behavior.
