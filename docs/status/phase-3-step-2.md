# Phase 3 Step 2 — Context Window Budgeting

**Date:** 2026-09-08  
**Status:** implemented

---

## Objective

Prevent unbounded conversation history from being sent to the LLM by selecting a
budgeted suffix of committed messages before `LLMContextAssembler` builds the
request.

---

## Architecture

```
ConversationRepository.list_messages()
        ↓
committed Messages
        ↓
committed_messages_to_llm()
        ↓
ContextBudgetPolicy.select_history()   # when max_input_tokens is set
        ↓
LLMContextAssembler.assemble()
        ↓
LLMRequest → existing provider stream
```

| Component | Responsibility |
| --- | --- |
| `LLMRuntimeConfig.max_input_tokens` | Optional budget; `None` disables budgeting (default) |
| `approximate_token_count` | Provider-neutral ~4 chars/token estimate |
| `ContextBudgetPolicy` | Reserve system + current user; keep newest complete history that fits |
| `LLMContextAssembler` | Applies policy when configured; still pure/deterministic |
| `ContextBudgetExceededError` | Raised when system or current user alone exceed budget |

---

## Token estimation

`approximate_token_count` is an **estimate**, not a provider-accurate tokenizer.
Formula: empty → 0; otherwise `max(1, ceil(len(text) / 4))`.

Isolated behind `TokenEstimator` so an exact tokenizer can replace it later
without rewriting the selection algorithm.

---

## Selection algorithm

1. Estimate system instructions; if > budget → fail.
2. Estimate current user text; if > remaining → fail.
3. Walk committed LLM history from newest to oldest.
4. Include each complete message while it fits; stop at the first that does not.
5. Return the selected messages in original order (a history suffix).
6. Assembler appends the current user message exactly once.

Does **not**: mutate history, reorder messages, truncate message bodies,
summarize, or touch persistence/providers.

---

## Backward compatibility

Existing `LLMRuntimeConfig(...)` call sites without `max_input_tokens` keep
full-history behavior (budgeting disabled).

---

## Deferred

- Exact provider/model tokenizers
- Conversation summarization
- RAG / long-term memory
- Per-message content truncation
- Wiring `max_input_tokens` from AgentVersion control-plane UI
