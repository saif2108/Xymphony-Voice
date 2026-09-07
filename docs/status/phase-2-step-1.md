# Phase 2 Step 1 — Agent Runtime Core

**Date:** 2026-09-07  
**Status:** implemented. Provider orchestration primitives only — no STT, LLM, TTS, RAG, tools, memory, or workflows.

---

## Objective

Build the provider-agnostic **Agent Runtime** core that will eventually orchestrate:

`STT → Reliability/Repair → LLM → Tools/RAG/Memory → TTS`

This step implements runtime orchestration primitives only. `MinimalTransportSession` and `RuntimeWorkerSession` (Phase 1) remain unchanged and separate from media transport.

---

## Runtime responsibilities

| Component | Responsibility |
| --- | --- |
| `AgentRuntime` | Start/stop session, accept runtime inputs, create/manage turns, admit contract events, coordinate cancellation |
| `RuntimeContext` | Session/tenancy identity, monotonic event sequence, cancelled turn set, shutdown signal |
| `RuntimeTurn` | In-process turn lifecycle with explicit state machine |
| `RuntimeInput` | Typed runtime input dispatch (text, speech markers, cancel, shutdown, error) |
| `dispatch` | Build `xymphony_contracts.Event` envelopes (no second event bus) |
| `streaming` | Minimal `RuntimeStreamChunk` + `IncrementalOutputSink` for future provider streaming |

---

## Architecture

```
RuntimeInput
    ↓
AgentRuntime
    ↓
RuntimeTurn (turn-scoped)
    ↓
Event admission (xymphony_contracts.Event)
    ↓
IncrementalOutputSink (future LLM/TTS streaming)
```

`MediaTransport` / LiveKit remain in `xymphony_realtime` — not imported by AgentRuntime core.

---

## Turn abstraction

In-process `RuntimeTurn` maps to contract `Turn`:

| Runtime state | Contract `TurnStatus` |
| --- | --- |
| `created` | `in_progress` |
| `active` | `in_progress` |
| `completed` | `committed` |
| `cancelled` | `cancelled` |
| `failed` | `failed` |

Allowed transitions:

```
CREATED → ACTIVE → COMPLETED
                 → CANCELLED
                 → FAILED
```

Invalid transitions raise `InvalidStateTransitionError`.

---

## RuntimeContext

Carries:

- `session_id`, `organization_id`, `project_id`, `agent_id`, `agent_version_id`
- `config_hash`, `channel`, `deployment_id`
- monotonic event and turn sequence counters
- `cancelled_turn_ids` for stale-event filtering
- asyncio shutdown event

No provider SDK objects or secrets.

---

## Event dispatch

- Runtime inputs handled via `AgentRuntime.handle_input(RuntimeInput)`
- Contract events built with `dispatch.build_event()` and admitted via `AgentRuntime.admit_event()`
- Uses existing `Event.is_stale_for_cancelled_turns()` — stale LLM/TTS events from cancelled turns are dropped
- Session-level events (`SessionStarted`, `SessionEnded`, `Error`) do not require `turn_id`

Supported inputs (Step 2.1):

- `text_input` — creates/completes a turn (placeholder processing, no LLM)
- `user_speech_started` / `user_speech_ended` — turn + VAD-shaped contract events (no STT)
- `cancel_turn` — barge-in / interruption
- `shutdown` — graceful runtime stop
- `error` — runtime-level failure handling

---

## Cancellation semantics

- Session **stays active** after turn cancellation (`SessionStatus.ACTIVE`)
- Cancellation is **turn-scoped** via `turn_id`
- Cancelled turn IDs tracked in `RuntimeContext.cancelled_turn_ids`
- New turns can start after cancellation
- Stale provider/runtime results for cancelled turns are ignored via contract stale rules + `emit_stream_chunk()` guard

---

## Error handling

| Error | When |
| --- | --- |
| `InvalidRuntimeInputError` | Bad input or wrong session state |
| `InvalidStateTransitionError` | Illegal turn transition |
| `RuntimeNotRunningError` | Input before `start()` |
| `StaleTurnEventError` | Completing a cancelled turn |

Structured logging includes `session_id`, `turn_id`, event type — never secrets or full conversation text.

---

## Files created / modified

| Path | Change |
| --- | --- |
| `packages/agent-runtime/src/xymphony_runtime/runtime.py` | **created** — `AgentRuntime` |
| `packages/agent-runtime/src/xymphony_runtime/context.py` | **created** |
| `packages/agent-runtime/src/xymphony_runtime/turn.py` | **created** |
| `packages/agent-runtime/src/xymphony_runtime/input.py` | **created** |
| `packages/agent-runtime/src/xymphony_runtime/dispatch.py` | **created** |
| `packages/agent-runtime/src/xymphony_runtime/streaming.py` | **created** |
| `packages/agent-runtime/src/xymphony_runtime/errors.py` | **created** |
| `packages/agent-runtime/src/xymphony_runtime/__init__.py` | **modified** — exports |
| `tests/unit/runtime/test_agent_runtime.py` | **created** |
| `tests/unit/runtime/test_turn_lifecycle.py` | **created** |
| `docs/status/phase-2-step-1.md` | **created** |

Phase 1 files (`session.py`, `worker.py`, transport packages) unchanged.

---

## Tests

| Command | Result |
| --- | --- |
| `pytest tests/unit/runtime tests/unit/realtime` | **26 passed** |
| `ruff check .` | **passed** |
| `mypy` | **passed** (47 source files) |

No Docker, PostgreSQL, LiveKit Cloud, or external APIs required.

---

## Known limitations

- No provider adapters (STT/LLM/TTS)
- No persistence to PostgreSQL
- No wiring between `AgentRuntime` and `MinimalTransportSession` yet
- Text turn completes immediately (placeholder — no reasoning loop)
- No full observability/evaluation pipeline

---

## Intentionally NOT implemented

| Capability | Status |
| --- | --- |
| STT | **NOT IMPLEMENTED** |
| LLM | **NOT IMPLEMENTED** |
| TTS | **NOT IMPLEMENTED** |
| RAG | **NOT IMPLEMENTED** |
| Tools | **NOT IMPLEMENTED** |
| Memory | **NOT IMPLEMENTED** |
| Workflows | **NOT IMPLEMENTED** |
| LiveKit Agents | **NOT USED** |
| LangGraph / MCP / Redis / Kafka / Celery | **NOT ADDED** |

---

## Next step (not started)

Phase 2 Step 2 — provider port wiring and real adapter integration (per roadmap). **Not started.**
