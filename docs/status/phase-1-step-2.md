# Phase 1 Step 2 — Backend foundation, Postgres, Agent CRUD

**Date:** 2026-09-07  
**Status:** implemented. Realtime/LiveKit/adapters/dashboard were not added.

---

## What was implemented

- Docker Compose **PostgreSQL** (`pgvector/pgvector:pg16`) with volume + healthcheck
- FastAPI app in `apps/api` (`xymphony_api`)
- Alembic migrations
- `GET /v1/health` (liveness + `SELECT 1`)
- Agent CRUD and AgentVersion create/list/get/patch-draft/publish
- Mapping ORM rows ↔ `xymphony_contracts.Agent` / `AgentVersion`
- Layering: routes → `AgentService` → repositories → SQLAlchemy
- No provider secrets in version JSON (contract validators)

Auth is **not** implemented. Tenancy still exists: every query is scoped by `organization_id` + `project_id` from the project in the URL. A local-dev org/project is seeded by migration.

API paths follow [api-design.md](../api-design.md) (`/v1/projects/{pid}/agents/...`), not a flat `/v1/agents` tree. `DELETE` was added (requested for this step; not listed in the original API sketch). `GET .../versions/{id}` and `POST .../publish` exist so published snapshots can be frozen and retrieved.

---

## Files created

- `docker-compose.yml`, `.env.example`
- `apps/api/` — package, Alembic, FastAPI
- `tests/integration/` — health, agents, versions, migrations
- `tests/unit/api/` — mapping + health schema
- `docs/status/phase-1-step-2.md`

## Files modified

- `pyproject.toml` — workspace member `apps/api`, pythonpath, ruff ignores
- `README.md`, `CLAUDE.md`
- `docs/data-model.md`, `docs/api-design.md` — status lines only

---

## Database / migrations

Engine: PostgreSQL 16 + pgvector **image** (vector extension not enabled yet; no chunk table).

Alembic revision: `0001_p1_control_plane`

Tables:

- `organizations` (seed: Local Development / `local`)
- `projects` (seed: Default Project / `default`)
- `agents` — identity only (name, description, status, tags, tenancy, timestamps)
- `agent_versions` — snapshot: instructions, personality, locale, `llm`/`stt`/`tts` JSONB, `config_hash`, `version_n`, status, `published_at`

Constraints: `uq_projects_org_slug`, `uq_agent_versions_agent_n`, FKs with `ON DELETE CASCADE`.

Dev seed IDs:

- org `00000000-0000-4000-8000-000000000001`
- project `00000000-0000-4000-8000-000000000002`

Tests use database `xymphony_test` (created if missing) and `TRUNCATE ... CASCADE` per test.

---

## API endpoints

| Method | Path |
| --- | --- |
| GET | `/v1/health` |
| POST | `/v1/projects/{project_id}/agents` |
| GET | `/v1/projects/{project_id}/agents` |
| GET | `/v1/projects/{project_id}/agents/{agent_id}` |
| PATCH | `/v1/projects/{project_id}/agents/{agent_id}` |
| DELETE | `/v1/projects/{project_id}/agents/{agent_id}` |
| POST | `/v1/projects/{project_id}/agents/{agent_id}/versions` |
| GET | `/v1/projects/{project_id}/agents/{agent_id}/versions` |
| GET | `/v1/projects/{project_id}/agents/{agent_id}/versions/{version_id}` |
| PATCH | `/v1/projects/{project_id}/agents/{agent_id}/versions/{version_id}` (draft only) |
| POST | `/v1/projects/{project_id}/agents/{agent_id}/versions/{version_id}/publish` |

Errors: `{code, message, request_id, details?}`. Published PATCH → `409 conflict_published_immutable`.

---

## Tests

Unit (no Postgres): mapping, health schema, existing contracts — **40 passed** in this environment.

Integration (needs Postgres on `localhost:5432`):

- `tests/integration/test_health.py`
- `tests/integration/test_agents.py`
- `tests/integration/test_agent_versions.py`
- `tests/integration/test_migrations.py`

**Not executed here:** Docker and PostgreSQL were not available on the agent machine (`docker` missing; port 5432 closed). Run after `docker compose up -d postgres`.

Quality: `ruff check` and `mypy` (contracts + `xymphony_api`) passed.

---

## Commands

See README “Local development”.

```
docker compose up -d postgres
python -m alembic -c apps/api/alembic.ini upgrade head
python -m uvicorn xymphony_api.main:app --app-dir apps/api/src --reload
python -m pytest tests
```

---

## Architectural decisions

1. Nested project routes (api-design) rather than flat `/v1/agents`.
2. Sync SQLAlchemy 2 + psycopg3 (simplest FastAPI + Alembic path). Async later if needed.
3. Organizations/projects tables now (tenancy FKs), not deferred — required for isolation without inventing a global agent.
4. No Redis/LiveKit/auth IdP in Compose.
5. Publish freezes the same row (`published_at` set). Further PATCH of config is rejected. New edits → new `version_n`.
6. `config_hash` stored on insert/update of drafts via contract `with_config_hash()`.
7. Business logic in `AgentService`, not route handlers.

---

## Unresolved

- Identity provider (U-001) — still no login; APIs are open.
- Integration tests need Docker Compose (or any Postgres matching `.env.example`).
- No OpenAPI TypeScript generation yet.
- Sessions/messages tables still future (P1 later steps).

---

## Next recommended step

**Phase 1 Step 3 (M2):** do **not** start until Postgres is running and `pytest tests` including `tests/integration` is green on a developer machine.

Then: LiveKit room join / runtime-worker echo — still no real STT/LLM/TTS.
