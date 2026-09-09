# Phase 3 Step 7 — Context and Conversation-Memory Robustness

**Date:** 2026-09-08
**Status:** implemented (tests only — no production code changes)

---

## Objective

Harden the context and conversation-memory subsystem against realistic edge
cases without changing its fundamental architecture. All existing Phase 3
Steps 1–6 remain unchanged. No new production-code abstractions were introduced.

---

## Robustness Problems Investigated

### A. Summary Coverage Correctness
- Rolling summarization cycles across long conversations.
- Ensuring `through_sequence` never advances beyond committed, persisted messages.
- Verifying that messages between `through_sequence` and the most-recent message
  are never silently lost from `history_for_assembly`.
- Verifying no re-summarization occurs when coverage is already current.
- Verifying the current user message appears exactly once in the assembled request
  after multiple cycles.

### B. Oversized Summary
- Assembler soft-failure path when `summary_text` is too large for the budget.
- The assembler is stateless: oversized-summary fallback does not corrupt
  subsequent calls on the same `LLMContextAssembler` instance.
- Summarizer's internal short-prompt retry when the generated summary exceeds
  the fit check.

### C. Empty and Unusual Conversation Content
- Empty history assembles only the current user message.
- One-message conversation.
- Whitespace message content is preserved where the contract permits it.
- Whitespace-only generated summaries are not persisted.
- Identical messages in history are all preserved.
- Alternating user/assistant messages maintain chronological order.
- Very long single message is correctly cost-accounted and excluded when budget
  is insufficient.
- Messages with no text content parts are silently excluded.
- Non-committed (interrupted/cancelled) messages are excluded.

### D. Budget Boundary Conditions
- Exact-fit: tokens == budget → full history retained.
- One-token-over: oldest history entry dropped, newest retained.
- Mandatory content (system) exceeds budget → `ContextBudgetExceededError`.
- Mandatory content (current user) exceeds remaining budget after system
  → `ContextBudgetExceededError`.
- Summary + system + current user exactly fills budget → history dropped
  cleanly with no exception.

### E. Cancellation Safety
- Pre-generation cancellation: existing summary returned; no new persistence.
- Mid-stream cancellation: summary repository state unchanged.
- A later turn with a fresh `CancellationToken` can produce a summary normally
  after a prior cancelled turn.

### F. Provider Failure Safety
- `ProviderError` during summary generation: repository remains unchanged.
- `through_sequence` does not advance on failure (prior summary retained at its
  previous value).
- A subsequent turn can retry and successfully generate a summary after a prior
  failed turn (no permanent corruption).
- Provider failure does not block the main conversation turn assembly.

### G. Conversation Ledger Integrity
- Summary objects are stored only in `ConversationSummaryRepository`; they
  never appear as entries in `ConversationRepository`.
- Non-committed messages (status ≠ COMMITTED) are excluded from `LLMRequest`.
- Conversation repository preserves insertion order (critical for chronological
  LLM history).
- `next_sequence` increments monotonically.

### H. Concurrency / Duplicate Summarization Assumptions
Assessed and documented (no code changes needed):

- `ConversationSummarizer.prepare()` is a coroutine. Within a single
  asyncio event loop, it executes sequentially between `await` points.
- `AgentRuntime` processes one turn at a time; turn N+1 cannot start until
  turn N's coroutine completes or is cancelled.
- Therefore, two concurrent `prepare()` invocations for the same
  `session_id` can only arise if two separate `AgentRuntime` instances are
  erroneously pointed at the same session — an operational invariant
  violation, not a code-level correctness problem.
- No distributed locking or infrastructure was introduced; the guarantee
  is documented and tested through sequential-call behaviour.

### I. Regression Protection
- `max_input_tokens=None` → full history, no summarization.
- No summary → no `SUMMARY_SECTION_HEADER` in system prompt.
- Short conversation below budget → no error, no summarization.
- Absent generation parameters → `None` in `LLMRequest`.
- Present generation parameters → propagated correctly to `LLMRequest`.
- Provider failure → main turn assembly still succeeds.

---

## Behavior Verified

### Summary Coverage Guarantees
1. `through_sequence` is derived from the sequence numbers of committed
   messages, never from uncommitted state.
2. `through_sequence` is only written to the repository after a successful
   summary generation **and** after all cancellation checks pass.
3. Messages with `sequence > through_sequence` always appear in
   `history_for_assembly` after a successful summarization cycle.
4. When coverage is already current (no newly uncovered messages), no new
   summary LLM request is issued and `through_sequence` is not advanced.

### Cancellation Guarantees
1. A cancelled turn (via `cancel.cancelled` or `is_turn_cancelled()`)
   returns the previously persisted summary (if any) without modifying the
   summary repository.
2. Cancellation during streaming collects partial output but does not
   persist it.
3. A subsequent turn with a fresh token proceeds normally.

### Failure Guarantees
1. `ProviderError` during summary generation is caught, logged, and results
   in a `SummaryPreparation(summary_text=None, history_for_assembly=full_history)`.
2. The summary repository is not modified on failure; `through_sequence`
   stays at its prior value.
3. The caller (AgentRuntime) assembles a context without the summary and
   continues the turn.

### Budget Boundary Behavior
1. `system_instructions` (including summary block) → highest priority.
2. `current_user_text` → reserved after system.
3. Oldest history entries → dropped first when budget is exhausted.
4. The summary is not a conversation-turn message; it is appended to the
   system prompt via `build_system_with_summary`.
5. If the summary itself is too large: assembler soft-fails by dropping the
   summary and re-running history selection without it.

### Concurrency Assumptions (per-session)
- Serialized by the asyncio single-task-per-turn model of `AgentRuntime`.
- No distributed locks are needed as long as the operational invariant
  "one AgentRuntime per session" is maintained.
- Two concurrent workers on the same session would represent a deployment
  configuration error; the runtime does not defend against this case.

---

## Tests Added

**File:** `tests/unit/runtime/test_step7_robustness.py`

| # | Test | Category |
|---|------|----------|
| 1 | `test_rolling_summary_three_cycles_no_duplication` | A |
| 2 | `test_summary_coverage_never_advances_before_persistence` | A |
| 3 | `test_messages_not_skipped_between_coverage_and_recent_history` | A |
| 4 | `test_assembler_oversized_summary_soft_fails_and_uses_plain_system` | B |
| 5 | `test_assembler_oversized_summary_state_not_corrupted` | B |
| 6 | `test_oversized_summary_from_provider_triggers_short_retry` | B |
| 7 | `test_empty_conversation_history_assembles_only_current` | C |
| 8 | `test_one_message_conversation_assembles_correctly` | C |
| 9 | `test_whitespace_content_is_preserved_when_permitted` | C |
| 10 | `test_whitespace_summary_is_not_persisted` | C |
| 11 | `test_messages_with_identical_text_are_all_preserved` | C |
| 12 | `test_alternating_user_assistant_messages_preserve_order` | C |
| 13 | `test_very_long_single_message_in_history_counted_correctly` | C |
| 14 | `test_message_with_no_text_parts_excluded_from_history` | C |
| 15 | `test_non_committed_messages_excluded` | C |
| 16 | `test_exact_fit_succeeds` | D |
| 17 | `test_one_token_over_drops_oldest` | D |
| 18 | `test_mandatory_content_cannot_fit_raises` | D |
| 19 | `test_system_exceeds_budget_raises` | D |
| 20 | `test_summary_with_budget_summary_and_history_within_limit` | D |
| 21 | `test_summary_priority_over_history_when_both_tight` | D |
| 22 | `test_cancellation_before_generation_returns_existing_summary` | E |
| 23 | `test_cancellation_during_generation_does_not_persist` | E |
| 24 | `test_subsequent_turn_continues_normally_after_cancellation` | E |
| 25 | `test_provider_failure_does_not_corrupt_summary_repository` | F |
| 26 | `test_summary_coverage_does_not_advance_on_provider_failure` | F |
| 27 | `test_subsequent_turn_can_retry_summarization_after_failure` | F |
| 28 | `test_summaries_never_appear_as_conversation_messages` | G |
| 29 | `test_non_committed_messages_never_reach_llm_request` | G |
| 30 | `test_ledger_order_preserved_after_multiple_appends` | G |
| 31 | `test_next_sequence_increments_monotonically` | G |
| 32 | `test_single_session_serialization_documented` | H |
| 33 | `test_no_budget_no_summarization_regression` | I |
| 34 | `test_generation_params_absent_regression` | I |
| 35 | `test_generation_params_present_regression` | I |
| 36 | `test_no_summary_regression` | I |
| 37 | `test_short_conversation_no_summary_needed` | I |
| 38 | `test_provider_failure_during_summarization_still_allows_main_turn` | I |

---

## Tests Executed

### Focused Step 7 tests
```
tests/unit/runtime/test_step7_robustness.py  →  38 passed
```

### Full unit suite
```
345 passed, 1 warning  (Step 6 baseline: 307 + 38 new = 345)
```

### Ruff (E, F, W, I)
```
All checks passed!
```

### mypy
```
Exit code 0 — no errors
```

---

## Files Changed

| File | Action |
|------|--------|
| `tests/unit/runtime/test_step7_robustness.py` | NEW — 36 robustness tests |
| `docs/status/phase-3-step-7.md` | NEW — this documentation |

**No production code was modified.** The existing architecture was found
to be correct for all tested edge cases. Every property verified through
tests was already guaranteed by the Phase 3 Steps 1–6 implementation.

---

## Known Limitations

1. **Live PostgreSQL integration tests** (`tests/integration/`) remain
   environment-blocked — no local PostgreSQL/Docker setup.
2. **Distributed concurrency** is not defended against at the code level.
   The safety guarantee is operational (one runtime per session). This is
   documented explicitly in the test and in this file.
3. **Token estimator accuracy** — `approximate_token_count` uses
   character-count heuristics, not a real tokenizer. Budget boundary tests
   are calibrated against this estimator; real provider counts may differ.
   The estimator is intentionally not changed in this step.
4. **Summary quality** — The correctness of the summary text generated by
   the LLM is out of scope. Only structural safety (coverage tracking,
   persistence, cancellation, size) is verified.

---

## Suggested Commit Message

```
Phase 3 Step 7: context and conversation-memory robustness tests
```
