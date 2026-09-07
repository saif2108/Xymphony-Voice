# Phase 2 Step 2 — LLM Provider Port + OpenAI Adapter

**Date:** 2026-09-07  
**Status:** implemented. LLM port, normalized types, OpenAI adapter, registry, and minimal runtime text→LLM streaming path only.

---

## Objective

Introduce a provider-agnostic **LLM port** and the first real adapter (OpenAI) without coupling `AgentRuntime` to any vendor SDK.

```
AgentRuntime
    ↓
LLMProvider (contracts port)
    ↓
packages/providers adapters
    ├── FakeLLMProvider (tests)
    └── OpenAILLMProvider
```

---

## Provider port

Defined in `packages/contracts/src/xymphony_contracts/llm.py`:

| Type | Purpose |
| --- | --- |
| `LLMProvider` | Protocol: `provider_key`, `stream(request, cancel=...)` |
| `LLMRequest` | Provider key, model, messages, system, params, tools |
| `LLMMessage` / `LLMRole` | Normalized chat messages |
| `LLMStreamChunk` | Streaming delta + optional finish reason |
| `LLMResponse` | Final normalized response (for future non-stream use) |
| `LLMToolCall` / `LLMToolDefinition` | Structured tool-call representation (future tools step) |
| `ProviderError` / `ProviderErrorCode` | Normalized provider failures |
| `CancellationToken` | Cooperative cancellation protocol |

Reuses contract `Usage` from `xymphony_contracts.usage` and event payloads `LLMTokenPayload` / `LLMResponsePayload`.

No vendor SDK imports in contracts or agent-runtime.

---

## Normalized types

All LLM port types are Pydantic models or protocols in `xymphony_contracts.llm`. Runtime events remain the source of truth via `xymphony_contracts.Event`.

---

## OpenAI adapter

Location: `packages/providers/src/xymphony_providers/openai_llm.py`

- Uses official `openai` Python SDK (`AsyncOpenAI`)
- API key from `OPENAI_API_KEY` only (via registry or direct construction in tests)
- Model from request or `OPENAI_MODEL` env default
- Streaming via `chat.completions.create(..., stream=True)`
- Maps SDK exceptions to `ProviderError` without leaking credentials
- Checks `CancellationToken` between chunks

---

## Factory / registry

Location: `packages/providers/src/xymphony_providers/registry.py`

```python
create_llm_provider(provider_key, *, model) -> LLMProvider
```

Currently supports `openai` only. Unknown keys raise `ProviderError(INVALID_REQUEST)`.

---

## Runtime integration

`AgentRuntime` accepts optional injected dependencies:

- `llm_provider: LLMProvider | None`
- `llm_config: LLMRuntimeConfig | None`

When both are set, text input follows:

```
RuntimeInput(TEXT) → begin turn → LLMProvider.stream → LLMToken events → LLMResponse event → complete turn
```

When omitted, Step 1 behavior is preserved (text input completes turn immediately with no LLM).

Runtime does **not** import or construct OpenAI. `EventCancellationToken` in `xymphony_runtime.cancellation` bridges turn cancellation to provider streams.

---

## Cancellation behavior

1. `_cancel_turn` sets `EventCancellationToken.cancel()` for the active LLM stream.
2. Provider loop exits without completing the turn.
3. Events for cancelled `turn_id` are dropped by existing `Event.is_stale_for_cancelled_turns()`.
4. A new turn is unaffected by stale chunks from a prior cancelled turn.

---

## Configuration

| Variable | Purpose |
| --- | --- |
| `OPENAI_API_KEY` | OpenAI API credential (required for real adapter) |
| `OPENAI_MODEL` | Default model when not specified in request/config |

Placeholders added to `.env.example` only — never commit real keys.

`LLMRuntimeConfig` carries non-secret runtime settings (provider_key, model, system_instructions, params).

---

## Tests

| Suite | Coverage |
| --- | --- |
| `tests/unit/providers/test_fake_llm.py` | Fake provider streaming, cancellation, errors |
| `tests/unit/providers/test_openai_llm.py` | Mocked SDK chunk normalization, error mapping, no key leakage |
| `tests/unit/providers/test_registry.py` | Unknown provider, missing key |
| `tests/unit/runtime/test_agent_runtime_llm.py` | Injected fake provider, tokens, errors, cancellation, sequential turns |
| Phase 1 runtime tests | Unchanged (no LLM provider injected) |

No network calls in normal pytest runs.

---

## Optional smoke test

`tests/integration/test_openai_llm_smoke.py`

Run only when explicitly enabled:

```bash
OPENAI_INTEGRATION=1 OPENAI_API_KEY=... pytest tests/integration/test_openai_llm_smoke.py -m openai
```

Skipped by default. Does not require credentials in CI.

---

## Known limitations

- Text input path only; speech turns do not invoke LLM yet.
- No tool execution, RAG, memory, or multi-turn conversation history assembly.
- OpenAI chat completions streaming only; usage not yet attached to `LLMResponse` events.
- Registry is minimal (not a plugin marketplace).
- No STT/TTS adapters in this step.

---

## Explicitly not implemented

STT, TTS, RAG, tools, memory, workflows, MCP, LiveKit Agents, LangGraph, PostgreSQL session persistence.

---

## Validation commands

```bash
pytest tests/unit/runtime tests/unit/realtime tests/unit/providers
ruff check .
mypy ...
```
