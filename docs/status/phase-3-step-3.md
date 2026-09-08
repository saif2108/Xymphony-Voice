# Phase 3 Step 3 — Conversation Summarization

**Date:** 2026-09-08  
**Status:** implemented

---

## Objective

Preserve older conversation context when the context budget would otherwise drop
it, using a session-scoped **derived** rolling summary.

---

## Key invariants

| Rule | Detail |
| --- | --- |
| Summary is derived state | Stored in `conversation_summaries`, never in `conversation_messages` |
| Conversation ledger is authoritative | Original messages are never deleted or modified for summarization |
| One rolling summary per session | Unique `session_id`; upsert replaces the active summary |
| Coverage tracking | `through_sequence` = last source message sequence covered |
| Lazy summarization | Runs only when `max_input_tokens` is set **and** budgeting would drop history |
| Soft failure | Provider/summary errors do not fail the assistant turn |
| Cancel-safe | Cancelled turns never persist a partial summary or advance coverage |

---

## Architecture

```
ConversationRepository.list_messages()
        ↓
if max_input_tokens set AND budget would drop history:
    ConversationSummarizer (lazy, same LLMProvider)
    → upsert ConversationSummary (through_sequence)
        ↓
summary_text + recent Messages + current user
        ↓
LLMContextAssembler (+ ContextBudgetPolicy)
        ↓
LLMRequest.system includes optional [Conversation summary] section
        ↓
existing LLM provider streaming
```

---

## `through_sequence` semantics

- Each ledger message carries a session-scoped sequence (metadata / DB order).
- An existing summary covers all messages with `sequence <= through_sequence`.
- Only messages with `sequence > through_sequence` among the would-be-dropped
  prefix are newly summarized.
- New rolling text may incorporate the previous summary plus newly uncovered
  messages.
- Coverage advances only after successful summarization **and** persistence.
- Repeated turns that uncover no new dropped messages reuse the stored summary.

---

## Trigger conditions

Summarization runs only when **all** of:

1. `max_input_tokens` is configured (budgeting enabled)
2. Committed history would exceed the budget under existing Step 2 policy
3. There is an uncovered dropped prefix (`sequence > through_sequence`)

Otherwise: Step 2 behavior is unchanged (no summary call).

---

## Summary representation & budgeting

Summary text is appended once to `LLMRequest.system`:

```
<existing system instructions>

[Conversation summary]
<summary text>
```

It is **not** a USER/ASSISTANT/SYSTEM ledger message and does not use a new
`LLMRole`.

Budget priorities (same `max_input_tokens`):

1. system instructions (+ summary section when present)
2. current user message
3. newest complete historical messages

If summary + system + current user leave no room, history may be empty.
If the summary itself cannot fit: try one shorter regenerate; otherwise soft-omit
the summary and continue with Step 2 budgeted history.

---

## Cancellation

Summarization is subordinate to the current assistant turn and uses the existing
turn cancellation token.

On cancel during summarization:

- stop/ignore remaining summary stream output where possible
- do **not** persist
- do **not** advance `through_sequence`
- stale summary results must not affect a later turn

---

## Soft failure

If summarization fails (provider error, empty output, oversized after retry):

- do not persist
- do not fail the user’s assistant turn solely for that reason
- log/record via existing conventions
- fall back to Step 2 budgeted recent-history assembly
- continue the normal LLM request

---

## Persistence

| Field | Purpose |
| --- | --- |
| `session_id` | Scope (unique active summary) |
| `organization_id` | Tenancy |
| `agent_version_id` | Audit / reproducibility |
| `through_sequence` | Coverage watermark |
| `summary_text` | Rolling summary body |
| `source_message_count` | Optional audit of messages folded in |
| `created_at` | Timestamp of last upsert |

Ports: `ConversationSummaryRepository.get_latest` / `upsert`.  
Adapters: in-memory (unit tests) + PostgreSQL.

Migration: `0003_p3_conversation_summaries` (additive; no backfill required).

---

## Limitations

- Same conversation model/provider is used for summarization (no dedicated
  cheaper summary model / separate provider config yet).
- No hierarchical or multiple concurrent summaries.
- No async background summarization jobs.
- No UI for viewing/editing summaries.
- No deletion/redaction of old messages.

---

## Out of scope (unchanged)

RAG, long-term user memory, tools, workflows, MCP, personality injection,
developer prompts, multi-agent behavior, LiveKit/media/STT/TTS architecture
changes.
