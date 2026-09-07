# Phase 2 Step 4 — TTS Provider Port + ElevenLabs Adapter

**Date:** 2026-09-07  
**Status:** implemented. TTS port, fake + ElevenLabs adapters, registry, and text→LLM→TTS runtime path only.

---

## Implementation summary

Added a provider-neutral **TTS port** and integrated streamed TTS into `AgentRuntime` on the existing text→LLM path:

```
text input → turn → LLM stream → LLMResponse → TTS stream → TTSChunk events → complete turn
```

Speech→STT and STT→LLM→TTS full voice pipelines are **not** implemented in this step.

---

## Files added

| File | Purpose |
| --- | --- |
| `packages/contracts/src/xymphony_contracts/tts.py` | TTS port types + `TTSProvider` protocol |
| `packages/agent-runtime/src/xymphony_runtime/tts_config.py` | `TTSRuntimeConfig` |
| `packages/providers/src/xymphony_providers/fake_tts.py` | Deterministic test adapter |
| `packages/providers/src/xymphony_providers/elevenlabs_tts.py` | ElevenLabs streaming adapter |
| `tests/unit/contracts/test_tts.py` | Contract tests |
| `tests/unit/providers/test_fake_tts.py` | Fake provider tests |
| `tests/unit/providers/test_elevenlabs_tts.py` | Mocked ElevenLabs tests |
| `tests/unit/providers/test_tts_registry.py` | Registry tests |
| `tests/unit/runtime/test_agent_runtime_tts.py` | Runtime integration tests |
| `tests/integration/test_elevenlabs_tts_smoke.py` | Optional gated smoke test |

---

## Files modified

| File | Change |
| --- | --- |
| `packages/contracts/src/xymphony_contracts/__init__.py` | Export TTS types |
| `packages/agent-runtime/src/xymphony_runtime/runtime.py` | TTS injection; text path LLM→TTS; cancellation |
| `packages/agent-runtime/src/xymphony_runtime/dispatch.py` | `tts_chunk_event` helper |
| `packages/agent-runtime/src/xymphony_runtime/__init__.py` | Export `TTSRuntimeConfig` |
| `packages/providers/src/xymphony_providers/registry.py` | `create_tts_provider` |
| `packages/providers/src/xymphony_providers/__init__.py` | Export TTS adapters |
| `packages/providers/pyproject.toml` | `elevenlabs>=1.0` dependency |
| `pyproject.toml` | `elevenlabs` pytest marker |
| `.env.example` | `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID` placeholders |

---

## Architecture decisions

- **Port types** mirror LLM/STT: `TTSRequest`, `TTSStreamChunk`, `TTSResponse`, `TTSTextRange`, `TTSProvider`.
- **Events use `audio_ref` only** — no raw PCM in `TTSChunkPayload` (matches existing contract).
- **`_run_llm_stream` returns assistant text** instead of completing the turn; orchestration moved to `_handle_text_input`.
- **Shared cancel token** for LLM+TTS on a text turn (parallel `_tts_cancel_tokens` dict, same pattern as Step 3).
- **ElevenLabs chosen** over Cartesia — aligns with existing `TTSBinding` default (`provider_key=elevenlabs`).
- **Injectable `stream_factory`** on ElevenLabs adapter for mock-based unit tests without network calls.

---

## Test results

| Suite | Result |
| --- | --- |
| Focused TTS tests | 18 new tests pass |
| Full unit suite (`pytest tests/unit`) | **120 passed** |
| Ruff | All checks passed |
| mypy | Success (63 source files) |

---

## Known limitations

- TTS only on **text→LLM** path when both LLM and TTS providers are configured.
- No LiveKit audio publish / speaker playback.
- No STT→LLM→TTS speech pipeline orchestration.
- ElevenLabs adapter uses sync SDK iterator wrapped in async provider (acceptable for Step 4).
- Optional ElevenLabs smoke test not run in CI/dev without credentials.

---

## Deferred work

- STT→LLM→TTS speech pipeline
- LiveKit outbound audio from `TTSChunk` refs
- PostgreSQL message/transcript persistence
- RAG, tools, workflows, MCP, VAD refinement
- Cartesia or additional TTS adapters

---

## Validation commands

```bash
pytest tests/unit/contracts/test_tts.py tests/unit/providers/test_fake_tts.py tests/unit/providers/test_elevenlabs_tts.py tests/unit/providers/test_tts_registry.py tests/unit/runtime/test_agent_runtime_tts.py
pytest tests/unit
ruff check .
mypy
```

Optional smoke:

```bash
ELEVENLABS_INTEGRATION=1 ELEVENLABS_API_KEY=... pytest tests/integration/test_elevenlabs_tts_smoke.py -m elevenlabs
```
