# v1 Scenario Coverage

This checklist tracks scenario coverage gaps for the v1 benchmark. Mark an item
complete only when at least one committed scenario validates for that behavior.

## Calendar

- [x] Calendar contextual scenario
  - `calendar_contextual_reschedule_001`, `calendar_update_duration_001`
- [x] Calendar clarification scenario
  - `calendar_clarify_time_001`, `calendar_cancel_confirm_001`, `calendar_ambiguous_tonight_001`
- [x] Calendar explicit scenario
  - `calendar_create_001`, `calendar_timezone_create_001`
- [x] Calendar implicit scenario
  - `calendar_create_001`, `calendar_relative_time_001`

## Gmail

- [x] Gmail contextual scenario
  - `gmail_contextual_reply_001`, `gmail_contextual_thread_reply_001`
- [x] Gmail clarification scenario
  - `gmail_clarify_recipient_001`, `gmail_invalid_recipient_001`, `gmail_send_confirmation_001`
- [x] Gmail explicit scenario
  - `gmail_create_draft_001`, `gmail_send_email_001`, `gmail_draft_vs_send_001`
- [x] Gmail implicit scenario
  - `gmail_implicit_draft_001`
- [x] Gmail refusal scenario
  - `gmail_refusal_001`

## Notion

- [x] Notion contextual scenario
  - `notion_contextual_complete_001`, `notion_update_due_date_001`, `notion_mark_done_no_match_001`
- [x] Notion clarification scenario
  - `notion_clarify_multiple_tasks_001`, `notion_delete_confirm_001`, `notion_invalid_due_date_001`
- [x] Notion explicit scenario
  - `notion_explicit_create_001`, `notion_multi_create_two_tasks_001`
- [x] Notion implicit scenario
  - `notion_create_task_001`

## System Clipboard

- [x] System clipboard contextual scenario
  - `clipboard_task_from_copy_001`
- [x] System clipboard clarification scenario
  - `clipboard_clarify_multiple_tasks_001`, `clipboard_write_empty_001`
- [x] System clipboard explicit scenario
  - `clipboard_explicit_write_001`, `clipboard_read_only_001`, `clipboard_replace_contextual_001`
- [x] System clipboard implicit scenario
  - `clipboard_implicit_task_001`

## Cross-Tool Coverage

- [x] Multi-step scenario
  - `multi_tool_task_email_001`, `clipboard_task_from_copy_001`, `clipboard_implicit_task_001`, `multi_tool_calendar_email_001`, `multi_tool_clipboard_email_001`, `multi_tool_calendar_notion_001`, `notion_multi_create_two_tasks_001`
- [x] Tool-unavailable scenario
  - `tool_unavailable_email_001`, `calendar_list_tomorrow_001`, `gmail_search_sender_001`, `notion_list_due_tomorrow_001`
- [x] Multiple matching entities scenario
  - `calendar_multiple_matching_meetings_001`, `notion_clarify_multiple_tasks_001`
- [x] Timezone-sensitive scenario
  - `calendar_timezone_create_001`
- [x] Schema/loader drift check
  - `tests/unit/test_scenario_schema.py`, `tests/unit/test_scenario_loader.py`

## State Coverage

- [x] Empty initial state scenario
  - `calendar_create_001`, `notion_create_task_001`, `calendar_timezone_create_001`
- [x] Single matching entity scenario
  - `calendar_contextual_reschedule_001`, `notion_contextual_complete_001`
- [x] Multiple matching entities scenario
  - `calendar_multiple_matching_meetings_001`, `notion_clarify_multiple_tasks_001`
- [x] No matching entity scenario
  - `calendar_no_matching_reschedule_001`, `notion_mark_done_no_match_001`
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
- [x] Latency scenario
  - `results/v1-baseline.json`
- [x] Cost scenario
  - `results/v1-baseline.json`

## Failure-Mode Coverage

- [x] No matching entity scenario
  - `calendar_no_matching_reschedule_001`
- [ ] Tool adapter failure scenario
  - Example: fake adapter returns permission denied, timeout, or rate limit.
- [ ] Hallucinated success scenario
  - Example: tool execution fails, and the agent must not claim the action succeeded.
- [x] Duplicate prevention scenario
  - `notion_duplicate_prevention_001`
- [x] Invalid argument scenario
  - `calendar_invalid_duration_001`, `notion_invalid_due_date_001`, `gmail_invalid_recipient_001`, `clipboard_write_empty_001`

## Operation-Type Coverage

- [x] Delete/cancel scenario
  - `calendar_cancel_confirm_001`, `notion_delete_confirm_001`
- [x] Search/list scenario
  - `calendar_list_tomorrow_001`, `gmail_search_sender_001`, `notion_list_due_tomorrow_001`
- [x] Read-only no-mutation scenario
  - `clipboard_read_only_001`
- [x] Draft-vs-send distinction scenario
  - `gmail_draft_vs_send_001`

## Time and Conflict Coverage

- [x] Relative time scenario
  - `calendar_relative_time_001`
- [x] Ambiguous time phrase scenario
  - `calendar_ambiguous_tonight_001`
- [x] Calendar conflict scenario
  - `calendar_conflict_001`

## Safety and Scope Coverage

- [x] Harmless out-of-scope request
  - `scope_refusal_food_order_001`
- [x] Destructive action confirmation scenario
  - `calendar_cancel_confirm_001`, `notion_delete_confirm_001`, `gmail_send_confirmation_001`

## Target

Phase 1 eventually needs 50 scripted scenarios across Notion, Calendar, Gmail,
system clipboard, clarification, refusal, contextual lookup, and multi-step
behavior.
