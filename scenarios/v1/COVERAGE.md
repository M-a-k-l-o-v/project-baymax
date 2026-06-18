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
  - `calendar_create_001`, `calendar_relative_time_001`
- [x] Calendar audio-path scenario
  - `calendar_audio_001`

## Gmail

- [x] Gmail contextual scenario
  - `gmail_contextual_reply_001`
- [x] Gmail clarification scenario
  - `gmail_clarify_recipient_001`
- [x] Gmail explicit scenario
  - `gmail_create_draft_001`
- [x] Gmail implicit scenario
  - `gmail_implicit_draft_001`
- [x] Gmail refusal scenario
  - `gmail_refusal_001`

## Notion

- [x] Notion contextual scenario
  - `notion_contextual_complete_001`
- [x] Notion clarification scenario
  - `notion_clarify_multiple_tasks_001`
- [x] Notion explicit scenario
  - `notion_explicit_create_001`
- [x] Notion implicit scenario
  - `notion_create_task_001`

## System Clipboard

- [x] System clipboard contextual scenario
  - `clipboard_task_from_copy_001`
- [x] System clipboard clarification scenario
  - `clipboard_clarify_multiple_tasks_001`
- [x] System clipboard explicit scenario
  - `clipboard_explicit_write_001`
- [x] System clipboard implicit scenario
  - `clipboard_implicit_task_001`

## Cross-Tool Coverage

- [x] Multi-step scenario
  - `multi_tool_task_email_001`, `clipboard_task_from_copy_001`, `clipboard_implicit_task_001`
- [x] Tool-unavailable scenario
  - `tool_unavailable_email_001`
- [x] Multiple matching entities scenario
  - `calendar_multiple_matching_meetings_001`, `notion_clarify_multiple_tasks_001`
- [ ] Timezone-sensitive scenario
  - Example: schedule across explicit timezone wording.
- [ ] Schema/loader drift check
  - Example: tests prove committed schema and Pydantic loader stay aligned.

## State Coverage

- [x] Empty initial state scenario
  - `calendar_create_001`, `calendar_audio_001`, `notion_create_task_001`
- [x] Single matching entity scenario
  - `calendar_contextual_reschedule_001`, `notion_contextual_complete_001`
- [x] Multiple matching entities scenario
  - `calendar_multiple_matching_meetings_001`, `notion_clarify_multiple_tasks_001`
- [x] No matching entity scenario
  - `calendar_no_matching_reschedule_001`
- [x] Duplicate existing entity scenario
  - `notion_duplicate_prevention_001`
- [x] Conflicting entity scenario
  - `calendar_conflict_001`

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
- [x] Duplicate prevention scenario
  - `notion_duplicate_prevention_001`
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

- [x] Relative time scenario
  - `calendar_relative_time_001`
- [ ] Ambiguous time phrase scenario
  - Example: "remind me tonight" should trigger clarification if no time rule exists.
- [x] Calendar conflict scenario
  - `calendar_conflict_001`

## Safety and Scope Coverage

- [x] Harmless out-of-scope request
  - `scope_refusal_food_order_001`
- [ ] Destructive action confirmation scenario
  - Example: user asks to delete/cancel something, and the agent should ask for confirmation if that is the product rule.

## Target

Phase 1 eventually needs 50 scripted scenarios across Notion, Calendar, Gmail,
system clipboard, clarification, refusal, contextual lookup, and multi-step
behavior.
