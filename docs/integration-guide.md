# Integration Guide

How two engineers and CI meet in the middle. **Phase 0: no code.** Phase 1 starts here.

---

## 1. Integration strategy

1. **Contracts first** — Event envelope, AgentVersion P1 JSON, Session DTO in `packages/contracts`.  
2. **Fakes** — `FakeLLM`, `FakeSTT`, `FakeTTS`, `FakeTransport` so dashboard and runtime integrate without keys.  
3. **Vertical slice daily** — a session can be started even if TTS is fake.  
4. **Compose is the shared environment** — do not develop against 6 different snowflake setups without documenting them.  
5. **Do not bypass abstractions** to demo (CLAUDE.md).

---

## 2. Suggested Phase 1 sequence

See [prototype-1.md](prototype-1.md) §9. Integration milestones:

| Milestone | Demo |
| --- | --- |
| M0 | Compose: API `/v1/health` + dashboard hello |
| M1 | Agent CRUD persists |
| M2 | LiveKit room join, agent hears silence / echo |
| M3 | Fake STT/LLM/TTS loop + transcript |
| M4 | Real adapters + barge-in |
| M5 | Persist session/messages + polish |

---

## 3. Control ↔ data handshake

```
Dashboard → POST /sessions → {token, room, session_id}   # API inserts sessions row (initializing)
Dashboard → LiveKit connect
LiveKit → runtime-worker job
Worker → GET /v1/internal/agent-versions/{id}/snapshot
Worker → UPDATE sessions (active/completed/failed) + INSERT turns/messages/events
Worker → events WS/SSE → Dashboard
```

**Snapshot load:** worker `GET` internal snapshot API (control plane is the only config writer).  
**Session row:** created by control plane on `POST /sessions` so the dashboard has a stable id before WebRTC connects.  
**Turns/messages/events + usage:** worker uses a **restricted database role** (update `sessions` status/usage; insert `turns`, `messages`, `events`). Do not dual-write those via public REST. Do not let the worker `UPDATE agent_versions`.

---

## 4. Frontend / backend boundary

Dashboard: presentation, LiveKit client.  
API: authz, CRUD, tokens.  
Runtime: loop.  
Shared: contracts + OpenAPI types.

---

## 5. Testing gates

PR: unit + contract.  
Nightly: realtime with keys if available.  
Definition: [definition-of-done.md](definition-of-done.md).

---

## 6. When architecture changes

1. Read `docs/decisions`  
2. Add/amend ADR  
3. Update glossary if terms change  
4. Update CLAUDE.md if rules change  
5. Then code
