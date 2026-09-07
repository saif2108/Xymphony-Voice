# Phase 2 Step 5 — End-to-End Text → LLM → TTS Runtime Pipeline

**Date:** 2026-09-07  
**Status:** implemented. Integration tests and documentation for the text→LLM→TTS pipeline established in Steps 2 and 4.

---

## Objective

Prove the runtime executes a complete assistant turn on the **text input path**:

```
RuntimeInput(TEXT)
  → create turn
  → LLMProvider.stream(...)
  → LLMToken events
  → LLMResponse
  → TTSProvider.stream(...)
  → TTSChunk events
  → turn COMPLETED / COMMITTED
```

This step is **integration**, not a new provider or orchestration framework. Runtime behavior was already wired in Phase 2 Step 4; Step 5 adds focused end-to-end tests, event-ordering guarantees, cancellation/failure coverage, and status documentation.

---

## Final text pipeline

When both `llm_provider` + `llm_config` and `tts_provider` + `tts_config` are injected:

1. `RuntimeInput.text_input(...)` begins a turn.
2. `_run_llm_stream` streams tokens, emits `LLMToken` events, then `LLMResponse`.
3. On successful LLM completion, assistant text is passed to `_run_tts_stream`.
4. TTS chunks are emitted as `TTSChunk` events.
5. `_complete_turn` marks the turn **COMPLETED** / **COMMITTED**.

If LLM fails, TTS is **not** invoked. If TTS fails after a successful LLM response, the turn is **FAILED** with a normalized `ERROR` event.

`AgentRuntime` does not instantiate vendors or read API keys; all providers remain injected via contracts.

---

## Event / lifecycle behavior

### Guaranteed ordering (within a successful text turn)

| Phase | Events |
| --- | --- |
| Turn start | Turn created; turn-scoped processing begins |
| LLM streaming | One or more `LLMToken` events |
| LLM complete | Single `LLMResponse` after all tokens |
| TTS streaming | One or more `TTSChunk` events **after** `LLMResponse` |
| Turn end | Turn **COMPLETED** / **COMMITTED** |

### Metadata guarantees (all admitted turn events)

- `session_id` matches runtime context
- `turn_id` matches the active turn
- Global `sequence` is monotonically increasing across the session (`validate_sequence_monotonic`)

Internal lifecycle events (e.g. speech-started on other paths) may interleave between turns; tests assert only contract-level guarantees above.

---

## Cancellation behavior

Reuses existing turn-scoped cancellation from Steps 1–4:

- **During LLM:** cancel token stops LLM stream; turn **CANCELLED**; TTS does not start.
- **During TTS:** cancel token stops TTS stream; turn **CANCELLED**; remaining chunks suppressed.
- **Stale events:** `LLMToken`, `LLMResponse`, and `TTSChunk` for a cancelled turn are rejected by admission (`STALE_IF_TURN_CANCELLED`).
- **Session:** remains **running**; a subsequent text input can complete a new turn without leakage from the cancelled turn.

---

## Failure / recovery behavior

| Scenario | Turn state | TTS invoked? | Session usable? |
| --- | --- | --- | --- |
| LLM failure | FAILED | No | Yes |
| TTS failure after LLM success | FAILED | Yes (fails) | Yes |
| Recovery on next turn | COMPLETED | Yes (if providers healthy) | Yes |

Provider errors are normalized to `ProviderError` and surfaced as `ERROR` events; errors are not swallowed.

---

## Files added

| File | Purpose |
| --- | --- |
| `tests/unit/runtime/pipeline_helpers.py` | Shared fake-provider runtime setup and ordering assertions |
| `tests/unit/runtime/test_agent_runtime_text_pipeline.py` | Step 5 end-to-end integration tests |
| `docs/status/phase-2-step-5.md` | This document |

---

## Files modified

None required for runtime behavior — Step 4 implementation is the source of truth.

---

## Tests and results

### Focused Step 5 tests

```bash
pytest tests/unit/runtime/test_agent_runtime_text_pipeline.py -v
```

Covers:

- End-to-end text → fake LLM → fake TTS → completed turn
- Event ordering (tokens before response before TTS chunks)
- Event metadata (session_id, turn_id, monotonic sequence)
- Multiple sequential text turns
- Cancellation during LLM (TTS never starts)
- Cancellation during TTS (partial output)
- Stale LLM/TTS output rejected for cancelled turn
- Session usable after cancellation + new turn
- LLM failure before TTS (TTS not invoked)
- TTS failure after LLM success
- Recovery after LLM failure
- Recovery after TTS failure

All tests use `FakeLLMProvider` and `FakeTTSProvider` — **no external API credentials**.

| Suite | Result |
| --- | --- |
| Focused Step 5 tests (`test_agent_runtime_text_pipeline.py`) | **11 passed** |
| Full unit suite (`pytest tests/unit`) | **131 passed** |
| Ruff | All checks passed |
| mypy | Success (63 source files) |

---

## Known limitations

- **Text path only** — no microphone, LiveKit, speaker playback, or STT→LLM automatic chaining.
- **STT unchanged** — speech/STT path exists for future voice pipeline work but is not part of this step.
- **No persistence** — turns/events are in-process only.
- **No RAG, tools, workflows, MCP, LangGraph, telephony, VAD, or barge-in.**

This step does **not** complete the realtime voice pipeline.

---

## Intentionally deferred

- Local/free providers (Ollama, Whisper, Piper)
- STT → LLM orchestration on speech turns
- Audio publish/subscribe and playback
- Postgres session/message persistence
- Authentication and multi-tenant API wiring
