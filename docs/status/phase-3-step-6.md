# Phase 3 Step 6 — Provider-Neutral LLM Generation Parameters

**Date:** 2026-09-08  
**Status:** implemented

---

## Objective

Implement provider-neutral handling and validation of core LLM generation controls (`temperature`, `max_output_tokens`, `top_p`) represented in `AgentVersion.llm.params`, ensuring deterministic validation during worker bootstrap and clean propagation through `LLMRuntimeConfig` and `LLMRequest` to provider adapters without leaking provider-specific concepts into runtime abstractions.

---

## Architecture

```
AgentVersion.llm.params (JSON bag in persisted snapshot)
        ↓
apps/runtime-worker/src/xymphony_runtime_worker/bootstrap.py
  (helpers: _llm_temperature, _llm_top_p, _llm_max_output_tokens)
        ↓
LLMRuntimeConfig (temperature, top_p, max_output_tokens)
        ↓
LLMContextAssembler.assemble() / Summarizer
        ↓
LLMRequest (strongly typed, bounds-validated generation fields)
        ↓
LLMProvider (OpenAILLMProvider, FakeLLMProvider, etc.)
        ↓
Provider-specific API/SDK arguments (e.g. OpenAI kwargs)
```

| Layer | Component | Responsibility |
| --- | --- | --- |
| Control Plane / Persistence | `AgentVersion.llm.params` | Persisted, immutable configuration bag |
| Worker Bootstrap | `runtime_configs_from_version()` | Deterministic extraction and type/range validation |
| Runtime Config | `LLMRuntimeConfig` | Decoupled configuration snapshot for runtime session |
| Context Assembly | `LLMContextAssembler.assemble()` | Passes normalized generation params to `LLMRequest` |
| Contracts | `LLMRequest` | Provider-neutral request interface with typed generation fields |
| Provider Adapter | `OpenAILLMProvider` | Maps normalized fields to provider-specific SDK arguments |

---

## Supported Normalized Parameters & Validation Rules

| Parameter | Type | Validation Rules | Default / Absent |
| --- | --- | --- | --- |
| `temperature` | `float` | Numeric (`int` or `float`), strictly `0.0 <= val <= 2.0`. Booleans, strings, and non-numeric types are rejected. | `None` (omitted from request) |
| `top_p` | `float` | Numeric (`int` or `float`), strictly `0.0 <= val <= 1.0`. Booleans, strings, and non-numeric types are rejected. | `None` (omitted from request) |
| `max_output_tokens` | `int` | Integer strictly `>= 1`. Booleans, floats, strings, and non-integers are rejected. Aliases `"max_output_tokens"`, `"max_completion_tokens"`, and `"max_tokens"` are recognized; conflicting values raise `ValueError`. | `None` (omitted from request) |

---

## Provider Adapter Mapping

### OpenAILLMProvider
- `request.temperature` → `kwargs["temperature"]`
- `request.top_p` → `kwargs["top_p"]`
- `request.max_output_tokens` → `kwargs["max_completion_tokens"]`
- Backward-compatible fallback: if request fields are `None`, inspection of `request.params` is maintained.

### What Remains Provider-Specific
- Custom vendor parameters (e.g., `seed`, `frequency_penalty`, `presence_penalty`, `logit_bias`) remain in `request.params` and are handled only inside concrete provider adapters.
- Provider adapters are responsible for translating normalized parameter names to their vendor's specific API requirements (e.g., mapping `max_output_tokens` to `max_completion_tokens` for modern OpenAI chat completions).

---

## Tests Executed

1. **Bootstrap & Helper Unit Tests** (`tests/unit/runtime_worker/test_voice_worker_integration.py`):
   - Absent parameters preserve `None`.
   - Valid values within range map cleanly to expected types (`int` or `float`).
   - Booleans rejected for all generation parameters.
   - Out-of-range values rejected (`temperature` outside `[0.0, 2.0]`, `top_p` outside `[0.0, 1.0]`, `max_output_tokens < 1`).
   - Non-numeric / non-integer types rejected.
   - Conflicting alias keys for max output tokens rejected.
   - `runtime_configs_from_version` propagates valid configurations and raises on invalid entries.

2. **Worker Runtime End-to-End Test** (`tests/unit/runtime_worker/test_voice_worker_integration.py`):
   - Verified that `AgentVersion.llm.params` populated with `temperature`, `top_p`, and `max_output_tokens` reach `LLMRequest` emitted to `FakeLLMProvider` during actual conversation turns.

3. **OpenAI Provider Tests** (`tests/unit/providers/test_openai_llm.py`):
   - Verified mapping of `request.temperature`, `request.top_p`, and `request.max_output_tokens` into `client.chat.completions.create` arguments.
   - Verified that absent generation parameters are cleanly omitted from call arguments.

4. **Contract Validation Tests** (`tests/unit/contracts/test_providers.py`):
   - Verified Pydantic field-level boundary validation on `LLMRequest`.

---

## Known Limitations

- Live PostgreSQL integration tests (`tests/integration/test_agent_versions.py`, etc.) remain environment-blocked due to lack of local PostgreSQL/Docker infrastructure.
- Dynamic per-turn generation parameter overrides (e.g., dynamically altering temperature mid-session based on conversation state) are deferred to future workflow/agent control phases; session-level AgentVersion snapshot configuration controls the runtime.
