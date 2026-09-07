# Phase 1 Step 4 — Runtime worker lifecycle

**Date:** 2026-09-07  
**Status:** implemented. No STT, LLM, TTS, conversational loop, RAG, tools, workflows, dashboard, or LiveKit Agents.

---

## Objective

Connect the existing runtime worker to the existing `MediaTransport` port and `MinimalTransportSession` so the **Xymphony runtime owns realtime session lifecycle** — connect, observe transport events, keep the session alive, and shut down cleanly.

---

## Architecture

```
Browser
   ↓
LiveKit Cloud
   ↓
LiveKitMediaTransport
   ↓
MediaTransport port (xymphony_contracts)
   ↓
MinimalTransportSession (xymphony_runtime)
   ↓
RuntimeWorkerSession (xymphony_runtime)
   ↓
Xymphony Runtime Worker CLI (apps/runtime-worker)
```

LiveKit remains **media transport only**. The runtime worker orchestrates lifecycle; it does not run STT/LLM/TTS or a conversational agent loop.

---

## Lifecycle

| Runtime state | Maps to `SessionStatus` | Meaning |
| --- | --- | --- |
| `initializing` | `initializing` | Session object created, handlers registered |
| `connecting` | — | Transport connect in progress |
| `connected` | `active` | Transport connected; session kept alive |
| `stopping` | — | Graceful shutdown in progress |
| `stopped` | `terminated` | Transport disconnected cleanly |
| `failed` | `failed` | Connect or unrecoverable transport failure |

State transitions are recorded as `LifecycleTransition` observations. Transport participant/error events are appended to the same observation stream (no second event system).

---

## Event flow

1. Worker starts `RuntimeWorkerSession.run(transport, config)`.
2. `MinimalTransportSession` registers transport handlers.
3. On connect success → lifecycle `connected`; transport may emit participant events.
4. Participant/error transport events are copied into `session.observations` and logged.
5. Session waits until transport disconnect **or** explicit shutdown (SIGINT/SIGTERM/`shutdown()`).
6. Pending wait tasks are cancelled; transport is disconnected; lifecycle ends in `stopped` or `failed`.

Contract `Event` envelopes (with full tenancy UUIDs) are **not** emitted yet — Step 4 surfaces transport/lifecycle observations only, preserving the existing event model for later persistence/UI.

---

## Shutdown / cancellation

- `RuntimeWorkerSession` installs SIGINT/SIGTERM handlers that call `shutdown()`.
- `shutdown()` sets an internal asyncio event; wait tasks are cancelled via `asyncio.gather(..., return_exceptions=True)`.
- `transport.disconnect()` is always attempted in `finally`, including after connect failure or mid-connect shutdown.
- Background wait tasks are tracked and cancelled; tests assert no dangling tasks after shutdown.

---

## Worker configuration

Uses existing environment variables (no hardcoded secrets):

| Variable | Purpose |
| --- | --- |
| `LIVEKIT_URL` | LiveKit Cloud WebSocket URL |
| `LIVEKIT_API_KEY` | API key (server/worker only) |
| `LIVEKIT_API_SECRET` | API secret (server/worker only) |
| `LIVEKIT_ROOM` | Room name (default `xymphony-dev`) |
| `LIVEKIT_WORKER_IDENTITY` | Worker participant identity |
| `XYMPHONY_SESSION_ID` | Optional session id |
| `LOG_LEVEL` | Logging level |

CLI flags override env defaults: `--room`, `--identity`, `--session-id`.

---

## Files created / modified

| Path | Change |
| --- | --- |
| `packages/agent-runtime/src/xymphony_runtime/lifecycle.py` | **created** — `RuntimeSessionLifecycleState` |
| `packages/agent-runtime/src/xymphony_runtime/observations.py` | **created** — runtime observation types |
| `packages/agent-runtime/src/xymphony_runtime/worker.py` | **created** — `RuntimeWorkerSession` |
| `packages/agent-runtime/src/xymphony_runtime/session.py` | **modified** — lifecycle, shutdown, observations |
| `packages/agent-runtime/src/xymphony_runtime/__init__.py` | **modified** — exports |
| `apps/runtime-worker/src/xymphony_runtime_worker/main.py` | **modified** — uses `RuntimeWorkerSession` |
| `packages/realtime/src/xymphony_realtime/fake_transport.py` | **modified** — `fail_on_connect` for tests |
| `tests/unit/runtime/test_minimal_session.py` | **modified** — Step 4 lifecycle tests |
| `tests/unit/runtime/test_worker_session.py` | **created** — worker orchestration test |
| `docs/status/phase-1-step-4.md` | **created** — this document |

---

## Tests run (Step 4) — verification

| Command | Result |
| --- | --- |
| `pytest tests/unit/runtime tests/unit/realtime tests/unit/api/test_dev_livekit.py` | **15 passed** |
| `ruff check .` | **passed** |
| `mypy` | **passed** (40 source files) |

---

- successful lifecycle transitions
- connect failure → `failed` + disconnect
- transport disconnect ends session
- shutdown during connected session
- participant event propagation via observations
- no dangling tasks after shutdown
- worker session orchestration

Regression: Step 3 realtime/API unit tests unchanged in scope.

No Docker/PostgreSQL required.

---

## Real smoke test (manual)

From repo root (with `.env` configured and `pip install -e apps/api` or workspace sync):

**Terminal A — worker**

```bash
py -m xymphony_runtime_worker.main --room xymphony-dev
```

**Terminal B — API + browser (Step 3 dev page)**

```bash
py -m uvicorn xymphony_api.main:app --app-dir apps/api/src --reload --port 8000
```

Open `http://localhost:8000/dev/livekit`, connect to the same room. Worker logs should show lifecycle `connected`, participant join/leave, and `stopped` on Ctrl+C.

Automated suite does **not** depend on LiveKit Cloud.

---

## Known limitations

- No control-plane session record persistence yet
- No contract `Event` envelope emission (observations only)
- No STT/LLM/TTS, turn loop, barge-in, or agent intelligence
- Step 2 Postgres/Docker integration tests remain blocked locally
- Production auth not implemented

---

## Explicit non-goals (Step 4)

- LiveKit Agents framework
- STT / LLM / TTS
- Conversational agent loop
- RAG, tools, workflows, memory, dashboard
- Kafka, Celery, Kubernetes, or other brokers

---

## Next step (not started)

Phase 2 / later Phase 1 items per roadmap — **not started in this step.**
