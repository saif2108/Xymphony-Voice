# Phase 2 Step 6 — MediaTransport ↔ AgentRuntime Bridge

**Date:** 2026-09-07  
**Status:** implemented. Transport-agnostic `RuntimeMediaBridge` connects MediaTransport lifecycle to AgentRuntime without vendor logic in either layer.

---

## Objective

Create a clean bridge between the realtime **MediaTransport** layer and **AgentRuntime** so transport observations become runtime inputs and runtime events are observable for future media publication — without implementing the full voice pipeline.

---

## What was implemented

| File | Purpose |
| --- | --- |
| `packages/agent-runtime/src/xymphony_runtime/bridge.py` | `RuntimeMediaBridge` — DI of `AgentRuntime` + `MediaTransport` |
| `packages/agent-runtime/src/xymphony_runtime/__init__.py` | Export `RuntimeMediaBridge` |
| `tests/unit/runtime/bridge_helpers.py` | Shared fake transport/runtime bridge setup |
| `tests/unit/runtime/test_runtime_media_bridge.py` | 12 focused bridge integration tests |
| `docs/status/phase-2-step-6.md` | This document |

`MinimalTransportSession` and `RuntimeWorkerSession` are **unchanged** — the worker CLI still uses transport-only lifecycle from Step 4. The bridge is the integration point for Phase 2+ agent execution over realtime transport.

---

## Architecture

```
MediaTransport (Fake / LiveKit adapter)
    ↓  connection / participant / error observations
RuntimeMediaBridge
    ↓  RuntimeInput (errors; text/speech via handle_input)
AgentRuntime
    ↓  contract Event envelopes
RuntimeMediaBridge (on_event listener)
    ↓  runtime_events / assistant_output_events
(future: transport audio publish)
```

### Bridge responsibilities

| Responsibility | Owner |
| --- | --- |
| WebRTC / room connect, disconnect | `MediaTransport` |
| Turn loop, LLM/STT/TTS, cancellation, stale events | `AgentRuntime` |
| Session lifecycle (connect → connected → stop) | `RuntimeMediaBridge` |
| Transport observations stream | `RuntimeMediaBridge.observations` |
| Runtime event observation | `RuntimeMediaBridge.runtime_events` |
| Forward caller inputs while connected | `RuntimeMediaBridge.handle_input` |

The bridge does **not** contain LiveKit SDK calls, provider SDK calls, or business logic.

---

## MediaTransport ↔ AgentRuntime interaction

### On `bridge.run(config)`

1. Register transport handlers (connection state, participant, error).
2. Register runtime `on_event` listener (single delivery path).
3. `await runtime.start()` → `SessionStarted`.
4. `await transport.connect(config)` → lifecycle `connected`.
5. Wait until transport disconnect **or** `bridge.shutdown()`.
6. Teardown: cancel wait tasks → `runtime.stop()` → `transport.disconnect()` → lifecycle `stopped` / `failed`.

### Transport → runtime (Step 6 minimal)

| Transport signal | Bridge action |
| --- | --- |
| Connect success | Lifecycle `connected`; runtime already started |
| Participant join/leave | Recorded in `observations` only |
| Transport error | `RuntimeInput.error(...)` + lifecycle `failed` |
| Connect exception | Normalized transport error + runtime error input |

Speech/audio transport signals are **not** mapped to runtime inputs in this step (STT/VAD deferred).

### Runtime → transport (Step 6 minimal)

- All admitted runtime events are appended once to `runtime_events`.
- Assistant output subset exposed via `assistant_output_events` (`LLMToken`, `LLMResponse`, `TTSChunk`).
- No audio is published to LiveKit yet — bridge is ready for a later publish step.

---

## Cancellation and stale events

- Turn cancellation is unchanged: callers use `bridge.handle_input(RuntimeInput.cancel_turn())`.
- Stale turn events remain suppressed by `AgentRuntime.admit_event` — the bridge does not bypass admission.
- `bridge.shutdown()` cancels background wait tasks before stopping runtime and disconnecting transport.

---

## Failure behavior

| Scenario | Bridge lifecycle | Runtime |
| --- | --- | --- |
| Transport connect failure | `failed` | Error input; stopped in teardown |
| Transport error while connected | `failed` | Error input |
| Provider turn failure (LLM/TTS) | `connected` (session continues) | Failed turn; session usable |
| Transport disconnect | `stopped` | `SessionEnded`; stopped |

Failures are logged and surfaced through `errors`, `observations`, and/or `runtime_events` — not swallowed.

---

## Test results

| Suite | Result |
| --- | --- |
| Focused Step 6 (`test_runtime_media_bridge.py`) | **12 passed** |
| Full unit suite (`pytest tests/unit`) | **143 passed** |
| Ruff | All checks passed |
| mypy | Success (64 source files) |

Tests use `FakeMediaTransport` + `FakeLLMProvider` / `FakeTTSProvider` — no Docker, Postgres, or external API credentials.

Coverage includes: start/connect, participant observations, text input → runtime events, no duplicate delivery, disconnect shutdown, connect failure, task cleanup, turn cancellation, stale suppression, provider failure recovery, lifecycle transitions, dependency injection.

---

## Architectural decisions

- **Bridge lives in `agent-runtime`** — imports only `MediaTransport` from contracts (same as `MinimalTransportSession`), not LiveKit SDKs.
- **Reuse observation types** from Step 4 (`LifecycleTransition`, transport participant/error events) — no duplicate event models.
- **Single runtime event listener** — satisfies “no duplicate event delivery” requirement.
- **Do not modify `LiveKitMediaTransport`** — transport adapters stay media-only.
- **Do not wire worker CLI yet** — avoids breaking Step 4 transport-only worker; bridge is tested in isolation.

---

## Intentionally deferred

- Microphone audio → STT
- STT → LLM automatic triggering on speech turns
- LLM → TTS → LiveKit speaker playback
- VAD, advanced turn detection, barge-in audio cancellation
- Real provider audio through LiveKit tracks
- Postgres session persistence, conversation history
- RAG, tools, workflows, MCP, authentication
- LiveKit Agents, Pipecat, LangGraph, message brokers

This step does **not** complete the realtime voice pipeline.

---

## Next step (not started)

Wire `RuntimeMediaBridge` into `apps/runtime-worker` and map transport audio frames to runtime STT input when the speech pipeline is ready.
