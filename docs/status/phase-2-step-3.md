# Phase 2 Step 3 — STT Provider Port + AssemblyAI Adapter

**Date:** 2026-09-07  
**Status:** implemented. STT port, normalized types, fake + AssemblyAI adapters, registry, and minimal speech→STT streaming path only.

---

## Objective

Introduce a provider-agnostic **STT port** and the first real adapter (AssemblyAI) without coupling `AgentRuntime` to any vendor SDK.

```
AgentRuntime
    ↓
STTProvider (contracts port)
    ↓
packages/providers adapters
    ├── FakeSTTProvider (tests)
    └── AssemblyAISTTProvider
```

---

## Provider port

Shared primitives extracted to `packages/contracts/src/xymphony_contracts/provider.py`:

- `ProviderErrorCode`, `ProviderError`, `CancellationToken`

STT types in `packages/contracts/src/xymphony_contracts/stt.py`:

| Type | Purpose |
| --- | --- |
| `STTProvider` | Protocol: `provider_key`, `transcribe(request, audio, cancel=...)` |
| `STTRequest` | Provider key, model, language, params |
| `STTAudioFrame` | Bounded synthetic PCM bytes + timing metadata |
| `STTTranscriptChunk` | Partial/final transcript chunk with timing/confidence |

`llm.py` re-exports shared provider primitives for backward compatibility.

---

## Runtime integration

`AgentRuntime` accepts optional injected dependencies:

- `stt_provider: STTProvider | None`
- `stt_config: STTRuntimeConfig | None`

When both are set, speech follows:

```
USER_SPEECH_STARTED → begin turn → start STT task + audio queue
AUDIO_FRAME → enqueue STTAudioFrame
USER_SPEECH_ENDED → close queue → await STT → TranscriptFrame events → complete turn
```

When omitted, Step 1 speech behavior is preserved (immediate turn completion, no STT).

Runtime does **not** import or construct AssemblyAI. No STT → LLM chaining in this step.

---

## Event mapping

| STT port output | Contract event |
| --- | --- |
| partial chunk | `TranscriptFrame` (`is_final=false`, `source=stt`) |
| final chunk | `TranscriptFrame` (`is_final=true`, `source=stt`) |
| provider failure | `Error` + failed turn |

`TranscriptFrame` added to `STALE_IF_TURN_CANCELLED`.

---

## AssemblyAI adapter

Location: `packages/providers/src/xymphony_providers/assemblyai_stt.py`

- Uses official `assemblyai` SDK (`AsyncRealTimeTranscriber`)
- API key from `ASSEMBLYAI_API_KEY` only
- Model from request or `ASSEMBLYAI_MODEL` env default
- Injectable session factory for unit tests (no network)
- Normalized `ProviderError`; credentials never logged

---

## Factory / registry

```python
create_stt_provider(provider_key, *, model) -> STTProvider
```

Currently supports `assemblyai` only.

---

## Configuration

| Variable | Purpose |
| --- | --- |
| `ASSEMBLYAI_API_KEY` | AssemblyAI credential |
| `ASSEMBLYAI_MODEL` | Default model slug |

Placeholders in `.env.example` only.

---

## Tests

| Suite | Coverage |
| --- | --- |
| `tests/unit/providers/test_fake_stt.py` | Fake streaming, cancellation, errors |
| `tests/unit/providers/test_assemblyai_stt.py` | Mocked session normalization |
| `tests/unit/providers/test_stt_registry.py` | Unknown provider, missing key |
| `tests/unit/runtime/test_agent_runtime_stt.py` | Injected fake, events, cancel, stale, sequential turns |
| `tests/unit/contracts/test_events.py` | Stale transcript after cancel |

Optional smoke: `tests/integration/test_assemblyai_stt_smoke.py` (`ASSEMBLYAI_INTEGRATION=1`).

---

## Known limitations

- Synthetic `RuntimeInput.audio_frame` only; no LiveKit audio ingestion
- No STT → LLM handoff
- No transcript persistence to PostgreSQL
- No VAD refinement
- AssemblyAI streaming session only

---

## Explicitly not implemented

LiveKit audio ingestion, MediaTransport changes, STT→LLM, TTS, RAG, tools, workflows, MCP, PostgreSQL persistence, full voice pipeline, LiveKit Agents.

---

## Validation commands

```bash
pytest tests/unit/providers tests/unit/runtime tests/unit/realtime tests/unit/contracts
ruff check .
mypy
```
