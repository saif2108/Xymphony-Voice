# Phase 2 Step 10 — Full Realtime Integration & Hardening

**Date:** 2026-09-07  
**Status:** implemented

---

## Objective

Connect browser microphone → LiveKit → worker → STT → session history → LLM → TTS → browser speaker using existing abstractions.

---

## Architecture

```
Browser mic/speaker
  ↔ LiveKit Cloud
  ↔ LiveKitMediaTransport
  ↔ RuntimeMediaBridge (barge-in on new speech)
  ↔ AgentRuntime (STT → LLM → TTS)
  ↔ Session/Conversation repositories (PostgreSQL via worker bootstrap)
```

Control plane: FastAPI + PostgreSQL  
Data plane: runtime worker + bridge + runtime + transport  
Providers: registry factories (OpenAI, AssemblyAI, ElevenLabs)

---

## Worker lifecycle

1. Load `XYMPHONY_SESSION_ID` from env/CLI (required UUID)
2. Open SQLAlchemy session; load pinned session + agent version
3. Build providers via registry (no direct SDK construction in worker)
4. Build `AgentRuntime` + `RuntimeMediaBridge` + `LiveKitMediaTransport`
5. Connect transport; wait for disconnect or SIGINT/SIGTERM
6. Teardown runtime, disconnect transport, commit/close DB session

---

## Barge-in

On `TransportAudioInputEvent.STARTED` while a non-terminal turn is active, bridge calls `RuntimeInput.cancel_turn()` before starting a new speech turn. Stale LLM/TTS events are dropped by existing admission guards; TTS output publish checks cancelled turns.

---

## Test results

| Suite | Result |
| --- | --- |
| Focused Step 10 (`test_voice_worker_integration.py` + updated `test_worker_session.py`) | **20 passed** |
| Full unit suite | **204 passed** |
| Integration (`tests/integration`) | **Not run** — PostgreSQL unavailable locally (fixture retries until timeout) |
| Ruff | All checks passed |
| mypy | Success (72 source files) |

---

## Manual LiveKit smoke test

**Not performed** in this environment — requires LiveKit Cloud credentials, provider API keys, PostgreSQL session row, and running worker + browser dev page concurrently.

Steps when configured:
1. `POST /v1/projects/{id}/sessions` → copy `session_id`
2. Set `XYMPHONY_SESSION_ID`, provider keys, `LIVEKIT_*`, `DATABASE_URL`
3. Run `xymphony-runtime-worker`
4. Open dev LiveKit page, connect, speak, verify audible response

- VAD / advanced endpointing
- Distributed workers, Kafka, K8s
- Auth, RAG, tools, MCP, telephony, multi-agent
- Full observability (OpenTelemetry)
- Full Voice Reliability / Repair Layer
