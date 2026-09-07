# Phase 1 Step 3 — LiveKit media transport foundation

**Date:** 2026-09-07  
**Status:** **complete and verified.** LiveKit is **media transport only** — not the Xymphony agent runtime. No LiveKit Agents framework, no STT/LLM/TTS.

---

## Verification summary

| Check | Result |
| --- | --- |
| LiveKit Cloud browser smoke test (`GET /dev/livekit`) | **PASS** — browser connected to LiveKit Cloud using server-side dev token minting |
| Targeted Step 3 unit tests | **8 passed** |
| `ruff check .` | **passed** |
| `mypy` | **passed** (37 source files) |

Real smoke test: Xymphony dev page at `/dev/livekit` successfully minted a participant token via `POST /v1/dev/livekit/token` and connected to LiveKit Cloud (project **Xymphony Voice Dev**) with credentials from `.env`. API secret was not exposed to the browser.

---

## Packaging fix (import path)

An earlier smoke-test blocker was:

```
ModuleNotFoundError: No module named 'xymphony_realtime'
```

**Root cause:** `xymphony-realtime` is a local workspace package (not on PyPI). `pip install -e apps/api` without local path dependencies did not install `packages/realtime`, so Uvicorn could not import `xymphony_realtime`.

**Fix:** Added repo-root-relative editable path dependencies and hatch direct-reference support:

- `apps/api/pyproject.toml` — `xymphony-contracts @ file:packages/contracts`, `xymphony-realtime @ file:packages/realtime`, plus `[tool.uv.sources]` and `[tool.hatch.metadata] allow-direct-references = true`
- `packages/realtime/pyproject.toml` — `xymphony-contracts @ file:packages/contracts`, plus matching uv/hatch metadata

Install from repo root:

```bash
pip install -e apps/api
# or: uv sync
```

Then run Uvicorn as documented below. No source duplication; package boundaries unchanged.

---

## What was implemented

- **`MediaTransport` port** in `xymphony_contracts.media_transport` — vendor-neutral lifecycle types and protocol
- **`xymphony_realtime`** package:
  - `FakeMediaTransport` for unit tests
  - `LiveKitMediaTransport` adapter using `livekit.rtc.Room` (not LiveKit Agents)
  - `mint_participant_token()` using `livekit-api` only
- **`xymphony_runtime`** — `MinimalTransportSession` orchestrates connect / participant events / disconnect
- **`xymphony_runtime_worker`** CLI — joins a LiveKit room via the port
- **Control-plane dev endpoints** (development only):
  - `POST /v1/dev/livekit/token?room=&identity=` — mints participant JWT server-side; never returns API secret
  - `GET /dev/livekit` — minimal browser connectivity test page
- Lifecycle handling: connection state, participant join/leave, transport errors, clean shutdown (SIGINT/SIGTERM + session shutdown)

---

## Architecture

```
Browser / Worker
       │
       ▼
MinimalTransportSession (xymphony_runtime)
       │
       ▼
MediaTransport port (xymphony_contracts)
       │
       ▼
LiveKitMediaTransport (xymphony_realtime) ──► LiveKit Cloud (WebRTC media)
```

The Xymphony runtime owns session lifecycle and will later attach STT/LLM/TTS adapters. LiveKit carries audio/media only ([ADR-001](../decisions/001-livekit-as-media-transport.md), [ADR-004](../decisions/004-runtime-vs-transport-separation.md)).

---

## Files created

| Path | Purpose |
| --- | --- |
| `packages/contracts/src/xymphony_contracts/media_transport.py` | Port types + protocol |
| `packages/realtime/` | LiveKit adapter + fake transport + token helper |
| `packages/agent-runtime/` | Minimal session orchestration |
| `apps/runtime-worker/` | Worker CLI entrypoint |
| `apps/api/src/xymphony_api/routes/dev_livekit.py` | Dev token endpoint |
| `apps/api/src/xymphony_api/routes/dev_pages.py` | Dev HTML page route |
| `apps/api/src/xymphony_api/static/dev/livekit.html` | Browser connectivity test |
| `tests/unit/realtime/` | Fake transport + token unit tests |
| `tests/unit/runtime/` | Minimal session lifecycle tests |
| `tests/unit/api/test_dev_livekit.py` | Dev token API tests |
| `tests/integration/test_livekit_connectivity.py` | Optional LiveKit Cloud test |

## Files modified

- `pyproject.toml` — workspace members, pytest/ruff/mypy paths
- `.env.example` — `LIVEKIT_*` variables
- `apps/api/` — config, schemas, main, dependencies, local workspace path deps
- `packages/realtime/pyproject.toml` — local workspace path deps for contracts

---

## Configuration

Copy `.env.example` → `.env` and set LiveKit Cloud credentials from project **Xymphony Voice Dev**:

```env
LIVEKIT_URL=wss://<project>.livekit.cloud
LIVEKIT_API_KEY=<api-key>
LIVEKIT_API_SECRET=<api-secret>
LIVEKIT_ROOM=xymphony-dev
LIVEKIT_WORKER_IDENTITY=xymphony-worker
XYMPHONY_ENV=development
```

Never commit real secrets. The API secret stays on the server/worker only.

---

## Run development realtime test

### 1. Install dependencies

From repo root:

```bash
pip install -e apps/api
# or: uv sync
```

### 2. Start runtime worker (terminal A)

```bash
uv run xymphony-runtime-worker --room xymphony-dev
```

Worker logs: `session_starting`, `livekit_connected`, `participant_event` when browser joins.

### 3. Start API (terminal B)

```bash
uv run uvicorn xymphony_api.main:app --reload --port 8000
```

(Postgres not required for dev token routes or Step 3 unit tests.)

### 4. Browser test

Open `http://localhost:8000/dev/livekit`, enter the same room name (`xymphony-dev`), click **Connect**.

Expected: token minted via API, browser joins LiveKit room, worker logs participant joined.

### Optional: LiveKit Cloud integration test

```bash
LIVEKIT_INTEGRATION=1 uv run pytest tests/integration/test_livekit_connectivity.py -m livekit
```

Requires valid `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` in the environment.

---

## Tests run (Step 3) — final verification

| Command | Result |
| --- | --- |
| LiveKit Cloud browser smoke test | **PASS** (manual, 2026-09-07) |
| `pytest tests/unit/realtime tests/unit/runtime tests/unit/api/test_dev_livekit.py` | **8 passed** |
| `ruff check .` | **passed** |
| `mypy` | **passed** (37 source files) |

Normal unit suite does **not** require LiveKit Cloud or PostgreSQL.

Optional pytest integration test (`LIVEKIT_INTEGRATION=1 pytest tests/integration/test_livekit_connectivity.py -m livekit`) remains available but was not required for Step 3 sign-off; browser smoke test covers end-to-end dev connectivity.

---

## Remaining blockers (outside Step 3)

- **Step 2 Postgres/Docker integration** — still blocked locally (Docker/PostgreSQL not installed); unchanged by Step 3
- **Production auth** — not implemented (dev token endpoint is development-only)
- **Step 4** — not started

---

## Explicit non-goals (Step 3)

- LiveKit Agents framework
- STT / LLM / TTS providers
- Production auth / session API
- Full Playground UI
- Docker / PostgreSQL setup for this step

---

## Next step (not started)

Phase 1 Step 4 — wire runtime session to control-plane session records and begin provider adapter stubs (per roadmap). **Not started in this checkpoint.**
