# Phase 2 Step 8 — Voice Output (TTS → MediaTransport)

**Date:** 2026-09-07  
**Status:** implemented. Assistant TTS audio is published through the transport layer.

---

## Objective

Complete the **output side** of the realtime voice pipeline:

```
AgentRuntime → LLM → TTS → TTSChunk events → RuntimeMediaBridge → MediaTransport → LiveKit → browser speaker
```

Event envelopes continue to use `audio_ref`; PCM bytes are resolved at the bridge/transport boundary.

---

## Architecture

| Layer | Responsibility |
| --- | --- |
| `AgentRuntime` | Existing LLM → TTS pipeline; `TTSChunk` events with `audio_ref` |
| `TTSOutputAudioResolver` | Optional port to resolve `audio_ref` → PCM (`FakeTTSProvider`, future real adapters) |
| `RuntimeMediaBridge` | On admitted `TTSChunk`, resolve audio and call `publish_audio_output` |
| `MediaTransport` | Publish `TransportAudioOutputFrame` (LiveKit `AudioSource` / fake capture list) |

---

## Output audio data flow

1. Runtime admits `TTSChunk` event (turn not cancelled).
2. Bridge listener schedules `_publish_tts_output`.
3. Resolver (`FakeTTSProvider.resolve_output_audio`) maps `audio_ref` → PCM.
4. Bridge builds `TransportAudioOutputFrame` (with `chunk_index`, `turn_id`).
5. Transport publishes:
   - **Fake:** appends to `published_output_frames`
   - **LiveKit:** `AudioSource.capture_frame` on published local track

---

## Cancellation / stale audio

- Cancelled turns do not admit new `TTSChunk` events → bridge never publishes them.
- Manually rejected stale events are never delivered to the bridge listener.
- Per-turn `chunk_index` resets for each new turn.

---

## Files changed

| File | Change |
| --- | --- |
| `packages/contracts/.../media_transport.py` | `TransportAudioOutputFrame`, `publish_audio_output` |
| `packages/contracts/.../tts.py` | `TTSOutputAudioFrame`, `TTSOutputAudioResolver` |
| `packages/providers/.../fake_tts.py` | `chunk_audio`, `resolve_output_audio` |
| `packages/realtime/.../fake_transport.py` | Outgoing audio capture |
| `packages/realtime/.../livekit_transport.py` | Outgoing `AudioSource` + publish |
| `packages/agent-runtime/.../runtime.py` | `voice_output_enabled` |
| `packages/agent-runtime/.../bridge.py` | TTS output publish path |
| `tests/unit/runtime/test_runtime_media_bridge_voice_output.py` | Step 8 tests |
| `tests/unit/runtime/bridge_helpers.py`, `voice_helpers.py` | Resolver wiring |
| `tests/unit/providers/test_fake_tts.py` | Resolver test |

---

## Test results

| Suite | Result |
| --- | --- |
| Focused Step 8 (`test_runtime_media_bridge_voice_output.py`) | **10 passed** |
| Full unit suite | **167 passed** |
| Ruff | All checks passed |
| mypy | Success (64 source files) |

---

## Manual browser spoken loop — remaining requirements

1. Wire `apps/runtime-worker` to use `RuntimeMediaBridge` with STT + LLM + TTS providers (not transport-only session).
2. Configure real TTS adapter with `resolve_output_audio` (ElevenLabs PCM resolution — not yet implemented).
3. Browser: connect via dev page (mic already enabled); subscribe to worker agent audio track.

---

## Deferred

- ElevenLabs (or other) production `resolve_output_audio` implementation
- Worker CLI voice wiring
- VAD, barge-in, Postgres, RAG, tools, auth
- Automated LiveKit Cloud end-to-end spoken loop test

Step 8 does **not** complete the full browser spoken loop without worker wiring + real TTS resolver.
