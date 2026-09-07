# Phase 2 Step 7 — Incoming Voice Pipeline (Transport → STT → AgentRuntime)

**Date:** 2026-09-07  
**Status:** implemented. Input-side voice pipeline only; TTS playback through LiveKit is Step 8.

---

## Objective

Begin the real incoming voice pipeline:

```
Browser microphone
      ↓
    LiveKit
      ↓
  MediaTransport
      ↓
 provider-neutral audio input
      ↓
       STT
      ↓
 TranscriptFrame
      ↓
 AgentRuntime
      ↓
 existing LLM path (and TTS events when configured)
```

This step handles **input only**. It does not publish assistant audio to the room.

---

## Architecture added

### Provider-neutral media input (`xymphony_contracts.media_transport`)

| Type | Purpose |
| --- | --- |
| `TransportAudioFrame` | Incoming PCM frame + participant/room metadata |
| `TransportAudioInputEvent` | Minimal speech boundary (`started` / `ended`) without VAD |
| `on_audio_frame` / `on_audio_input` | MediaTransport handler registration |

LiveKit SDK types remain inside `xymphony_realtime` adapters only.

### LiveKit audio ingestion (`LiveKitMediaTransport`)

- Subscribes to remote audio tracks on `track_subscribed`
- Streams frames via `rtc.AudioStream` into `TransportAudioFrame`
- Emits `TransportAudioInputEvent` STARTED/ENDED per track consumption lifecycle
- Cancels audio tasks on `track_unsubscribed`, room disconnect, and transport `disconnect`

### Fake transport (`FakeMediaTransport`)

- `simulate_audio_input_started` / `simulate_audio_frame` / `simulate_audio_input_ended`
- `simulate_speech_utterance` helper for tests

### Bridge (`RuntimeMediaBridge`)

Maps transport audio observations to existing runtime inputs when `runtime.speech_input_enabled`:

| Transport signal | Runtime input |
| --- | --- |
| `TransportAudioInputEvent.STARTED` | `RuntimeInput.user_speech_started()` |
| `TransportAudioFrame` | `RuntimeInput.audio_frame(...)` |
| `TransportAudioInputEvent.ENDED` | `RuntimeInput.user_speech_ended()` |

Guards ignore audio signals when no active turn or turn already terminal (e.g. after cancellation).

### AgentRuntime speech → LLM

After STT completes on a speech turn:

1. Read final `TranscriptFrame` from admitted events
2. Reuse `_run_assistant_pipeline` (same path as text input)
3. No duplicated LLM/TTS/turn-management logic

Speech-only turns (STT configured, LLM not) still complete after transcription as before.

---

## Exact speech/input data flow

```
TransportAudioInputEvent(STARTED)
  → bridge → RuntimeInput.user_speech_started()
  → AgentRuntime begins turn, starts STT stream task

TransportAudioFrame (repeated)
  → bridge → RuntimeInput.audio_frame(data, duration_ms, sample_rate_hz, channels)
  → STT audio queue → FakeSTTProvider / AssemblyAI adapter

TransportAudioInputEvent(ENDED)
  → bridge → RuntimeInput.user_speech_ended()
  → STT stream completes → TranscriptFrame events
  → final transcript → _run_assistant_pipeline → LLMToken / LLMResponse / (optional TTS)
  → turn COMPLETED
```

---

## Cancellation behavior

Unchanged from Steps 1–6:

- Turn cancel stops STT via cancel token
- Late `TranscriptFrame` events rejected for cancelled turns (`STALE_IF_TURN_CANCELLED`)
- Bridge ignores late transport ENDED/frame signals for terminal turns
- Session remains usable for subsequent speech turns

---

## Failure behavior

| Failure | Behavior |
| --- | --- |
| STT provider error | `Error` event; turn FAILED; session usable |
| LiveKit audio ingestion error | Transport error emitted; bridge forwards runtime error |
| Transport disconnect | Audio tasks cancelled; bridge teardown stops runtime |
| Bridge shutdown | Background tasks cancelled; no orphan ingestion tasks |

No raw audio or secrets logged.

---

## Files changed

| File | Change |
| --- | --- |
| `packages/contracts/src/xymphony_contracts/media_transport.py` | Audio input types + protocol handlers |
| `packages/realtime/src/xymphony_realtime/fake_transport.py` | Audio simulation + handlers |
| `packages/realtime/src/xymphony_realtime/livekit_transport.py` | Remote audio track ingestion |
| `packages/realtime/src/xymphony_realtime/__init__.py` | Export new contract types |
| `packages/agent-runtime/src/xymphony_runtime/input.py` | Audio frame sample rate/channels |
| `packages/agent-runtime/src/xymphony_runtime/runtime.py` | Speech→LLM via `_run_assistant_pipeline`; `speech_input_enabled` |
| `packages/agent-runtime/src/xymphony_runtime/bridge.py` | Transport audio → runtime input mapping |
| `tests/unit/runtime/voice_helpers.py` | Voice bridge/runtime test helpers |
| `tests/unit/runtime/test_runtime_media_bridge_voice.py` | 10 bridge voice integration tests |
| `tests/unit/runtime/test_agent_runtime_speech_llm.py` | 3 runtime speech→LLM tests |
| `tests/unit/realtime/test_fake_transport.py` | Audio handler test |
| `apps/api/src/xymphony_api/static/dev/livekit.html` | Enable microphone on connect (manual smoke) |

---

## Tests and results

| Suite | Result |
| --- | --- |
| Step 7 focused (`test_runtime_media_bridge_voice.py`, `test_agent_runtime_speech_llm.py`, audio fake transport) | **14 passed** |
| Full unit suite (`pytest tests/unit`) | **157 passed** |
| Ruff | All checks passed |
| mypy | Success (64 source files) |

All automated tests use `FakeMediaTransport` + `FakeSTTProvider` + `FakeLLMProvider` — no Docker, Postgres, AssemblyAI, or LiveKit Cloud credentials required.

---

## Manual LiveKit smoke test

Not run automatically in CI. To exercise transport audio ingestion manually:

1. Start API + runtime worker with `RuntimeMediaBridge` (future worker wiring) or existing transport worker
2. Open `http://localhost:8000/dev/livekit`
3. Connect — page now enables microphone publish
4. Verify worker logs show `livekit_audio_input_started` / `livekit_audio_frame_received` when a subscribed worker uses the bridge with STT configured

Full speech→STT→LLM through LiveKit requires worker wiring with STT/LLM providers and real or fake STT — deferred to operational setup, not automated in this step.

---

## Known limitations

- Track subscription lifecycle used as speech boundary — **not** utterance-level VAD/endpointing
- Worker CLI still uses transport-only `RuntimeWorkerSession` — bridge with voice must be wired explicitly
- No TTS audio publish to LiveKit (Step 8)
- No barge-in, telephony, Postgres persistence, RAG, tools, workflows, MCP, or authentication

---

## Intentionally deferred (Step 7)

- TTS → LiveKit speaker playback
- Complete conversational voice response loop
- Advanced VAD / turn detection / barge-in
- Real AssemblyAI through LiveKit in automated tests
- Production UI
- Postgres session persistence
- RAG, tools, workflows, MCP, authentication

Step 7 does **not** deliver microphone → spoken assistant reply end-to-end.
