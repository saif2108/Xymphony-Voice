# Phase 1 Step 1 — Domain contracts

**Date:** 2026-09-07  
**Status:** complete (contracts + unit tests). No runtime, LiveKit, adapters, or dashboard.

---

## What was implemented

Python monorepo foundation and `packages/contracts` (`xymphony_contracts`):

- P1 **Agent** / **AgentVersion** snapshots (frozen Pydantic models)
- **Session**, **Turn**, **Message**, **ContentPart**
- **Event** envelope (`schema_version=1`) and P1 payloads
- Provider **bindings** (`provider_key` + model / `voice_ref` + params) with no vendor SDK types
- Unit tests for validation, freeze/immutability, JSON round-trip, sequence, `turn_id`, stale-turn helper

---

## Files created

- `pyproject.toml` (workspace tooling: pytest, ruff, mypy)
- `packages/contracts/pyproject.toml`
- `packages/contracts/src/xymphony_contracts/` — `enums`, `providers`, `content`, `usage`, `agent`, `session`, `events`, `__init__`
- `tests/helpers.py`
- `tests/unit/contracts/test_*.py`
- `docs/status/phase-1-step-1.md` (this file)

## Files modified

- `CLAUDE.md` — current phase is Step 1 contracts, not “docs only”
- `README.md` — status, local test commands, docs index

No Phase 0 ADRs rewritten. No FastAPI app.

---

## Contract decisions

1. **P1 event catalog only.** Implemented: `AudioFrame`, `UserSpeechStarted`, `UserSpeechEnded`, `TranscriptFrame`, `LLMToken`, `LLMResponse`, `TTSChunk`, `AgentInterrupted`, `Error`, `SessionStarted`, `SessionEnded`. Deferred (documented NEAR/LATER): `TextFrame`, `ToolCall`, `ToolResult`, `WorkflowTransition`, `AgentTransferred`, `HumanTakeover`, `RetrievalResult`.
2. **AgentVersion is always a frozen snapshot object.** Draft vs published is `status`. In-memory mutation is rejected; updates use `model_copy`.
3. **P1 AgentVersion fields:** instructions, personality, locale, `llm` / `stt` / `tts` bindings, tenancy ids, `version_n`, timestamps, `config_hash`. No tool/knowledge/workflow/memory/guardrail fields (not required for P1).
4. **Bindings are slugs**, not vendor enums. Params reject credential-like keys. No secrets on the version.
5. **Session status has no `interrupted`.** Barge-in → Turn `cancelled` + Message `interrupted`; Session stays `active`.
6. **`sequence >= 1`.** Ordering is sequence, not timestamp.
7. **Turn-scoped P1 events require `turn_id`.** `SessionStarted` / `SessionEnded` / `Error` may omit it. `Error` is not treated as stale under cancel.
8. **`AudioFrame` uses `data_ref`, not PCM bytes** (serialization-safe; matches “no raw audio in contracts”).
9. **Channel enum includes later values** from the glossary (`web_embed`, `public_api`, `telephony`) so the type is stable; P1 sessions default to `playground`. This is a type catalog, not telephony implementation.
10. **`is_stale_for_cancelled_turns`** is a predicate on the contract, not an event loop.

---

## Assumptions

- Python 3.12+ (developed/tested on 3.13 via `py -3`).
- Root `pyproject.toml` is a uv-style workspace descriptor; this machine used `venv` + pip because `uv` was not on PATH.
- Example provider slugs in tests (`openai_compatible`, `assemblyai`, `elevenlabs`) are **test strings**, not adapters.
- `config_hash` is SHA-256 hex of canonical config JSON (no timestamps/secrets).

---

## Tests added

| File | Covers |
| --- | --- |
| `test_agent_version.py` | valid snapshot, frozen, copy-replace, empty instructions, publish rules, hash stability |
| `test_providers.py` | slug keys, secret params, empty model/voice, frozen bindings |
| `test_session.py` | no session `interrupted`, failed requires error_code, turn cancel vs session active, message interrupted |
| `test_events.py` | JSON round-trip, sequence, turn_id rules, payload mismatch, monotonic helper, stale LLM/TTS, Error not stale, interrupt id match |
| `test_import_isolation.py` | contracts import without FastAPI/LiveKit/vendor modules |

---

## Unresolved questions

Same as Phase 0 U-001–U-006 (identity, first live adapters, LiveKit Cloud vs OSS, uv vs pip). Not needed to ship contracts.

Whether to generate TypeScript types from these models in Step 2 or wait for OpenAPI.

---

## Known limitations

- No persistence, no FastAPI, no runtime loop.
- No provider **ports** (Protocol classes) yet — only selection bindings. Ports belong with the runtime/adapters package when those exist.
- Envelope `extra="ignore"` for forward compatibility; P1 payloads `extra="forbid"`.
- Channel enum lists future channels without implementing them.

---

## What Step 2 should implement

Per [integration-guide.md](../integration-guide.md) and [prototype-1.md](../prototype-1.md):

1. Compose skeleton: Postgres, Redis, API hello (`GET /v1/health`), dashboard hello (optional empty Next app **or** delay UI).
2. Control-plane **agent CRUD** using these contracts (Alembic + `agents` / `agent_versions` P1 tables).
3. Do **not** start LiveKit/STT/LLM/TTS until M2 after CRUD persists.

Do not implement the event loop in Step 2 unless the next task explicitly says so.

---

## Quality gates (this step)

- `pytest tests` — 37 passed
- `ruff check packages/contracts/src tests` — passed
- `mypy` on `xymphony_contracts` — passed
