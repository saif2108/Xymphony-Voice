# Xymphony Voice

**A platform for building, deploying, testing, and operating intelligent realtime AI agents.**

Voice-first. Text complementary. Provider-agnostic. Runtime-centric.

This repository is **not** an insurance-agent app and **not** a single-vendor voice demo.

---

## Current status

| Item | State |
| --- | --- |
| **Phase** | **Phase 3 complete — context / memory foundation** |
| **Application code** | Contracts, control-plane API, runtime worker, provider adapters, realtime transport, and dashboard. |
| **Remote** | `https://github.com/saif2108/Xymphony-Voice.git` |

Phase 0 exists so Phase 1 can **implement** instead of debating what Agent, Session, or barge-in mean.

Start here:

1. [docs/glossary.md](docs/glossary.md) — vocabulary  
2. [docs/architecture.md](docs/architecture.md) — master architecture  
3. [docs/prototype-1.md](docs/prototype-1.md) — what we build first  
4. [CLAUDE.md](CLAUDE.md) — rules for humans and coding agents  

---

## Product vision

Users will eventually: **create → configure → teach → connect → test → evaluate → publish → deploy → monitor → improve → version → rollback.**

Agents will operate over voice, text, and later files/images/video; on web, API, embed, and eventually telephony.

**P1 goal:** create an agent and talk to it in realtime (including interruption).

Full product: [docs/product-spec.md](docs/product-spec.md). Roadmap: [docs/roadmap.md](docs/roadmap.md).

---

## Architecture (short)

```
Dashboard (control plane UI)
    → FastAPI control plane (Postgres)
    → AgentVersion snapshot
    → Runtime worker (data plane)
         LiveKit ↔ VAD ↔ STT ↔ Agent Runtime ↔ LLM ↔ TTS
```

- **Our runtime is the product.** LiveKit transports audio ([ADR-001](docs/decisions/ADR-001-use-livekit.md)).  
- **Ports/adapters** for LLM/STT/TTS ([ADR-002](docs/decisions/ADR-002-provider-abstraction.md)).  
- **Control vs data plane** ([ADR-006](docs/decisions/ADR-006-control-data-plane.md)).  
- **Events** for cancellation, inspector, eval later ([ADR-004](docs/decisions/ADR-004-event-driven-runtime.md)).

ASCII diagrams and failure behavior: [docs/architecture.md](docs/architecture.md), [docs/runtime-design.md](docs/runtime-design.md).

---

## Technology direction

| Layer | Choice |
| --- | --- |
| API | Python, FastAPI, Pydantic |
| Dashboard | Next.js, React, TypeScript, Tailwind, shadcn/ui |
| Realtime media | LiveKit |
| Agent orchestration | Xymphony Agent Runtime; LangGraph only inside workflows later ([ADR-008](docs/decisions/ADR-008-langgraph-scope.md)) |
| DB | PostgreSQL + pgvector ([ADR-003](docs/decisions/ADR-003-postgres-pgvector.md)) |
| Cache / jobs | Redis; ARQ ([ADR-007](docs/decisions/ADR-007-async-jobs.md)) |
| Objects | S3-compatible / MinIO |
| Observability | OpenTelemetry |
| Containers | Docker Compose (not Kubernetes initially) |
| Tests | pytest, Playwright, realtime tests |

---

## Repository structure

**Today:** `docs/`, `packages/contracts/`, `packages/agent-runtime/`,
`packages/providers/`, `packages/realtime/`, `apps/api/`,
`apps/runtime-worker/`, `apps/dashboard/`, `docker-compose.yml`, and `tests/`.

Monorepo: [ADR-005](docs/decisions/ADR-005-monorepo.md). Do not add empty directories for show.

---

## Local development

Python 3.12+. From the repo root:

```
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e packages/contracts -e apps/api pytest ruff mypy httpx
copy .env.example .env
docker compose up -d postgres
.\.venv\Scripts\python.exe -m alembic -c apps/api/alembic.ini upgrade head
.\.venv\Scripts\python.exe -m uvicorn xymphony_api.main:app --app-dir apps/api/src --reload --port 8000
```

Health check: `GET http://localhost:8000/v1/health`

Local-dev tenant (seeded by migration):

- organization `00000000-0000-4000-8000-000000000001`
- project `00000000-0000-4000-8000-000000000002`

Example:

```
POST /v1/projects/00000000-0000-4000-8000-000000000002/agents
```

Tests (integration tests need Postgres on localhost:5432 and create a separate `xymphony_test` database):

```
.\.venv\Scripts\python.exe -m pytest tests
.\.venv\Scripts\ruff.exe check packages/contracts/src apps/api/src tests
.\.venv\Scripts\mypy.exe
```

---

## Development principles

- Build small, architect big.  
- Do not bypass abstractions for speed.  
- LLM reasons; tools/APIs/workflows decide deterministic facts.  
- Security and observability are designed in, not bolted on.  
- Horizons: NOW / NEAR / LATER / VISION — do not implement VISION in P1.  

Rules: [CLAUDE.md](CLAUDE.md). Done means: [docs/definition-of-done.md](docs/definition-of-done.md).

---

## Documentation index

| Doc | Contents |
| --- | --- |
| [docs/glossary.md](docs/glossary.md) | Canonical terms |
| [docs/architecture.md](docs/architecture.md) | System architecture |
| [docs/requirements.md](docs/requirements.md) | FR / NFR IDs |
| [docs/product-spec.md](docs/product-spec.md) | Product, journey, personas |
| [docs/runtime-design.md](docs/runtime-design.md) | Loop, barge-in, latency |
| [docs/event-model.md](docs/event-model.md) | Event envelope |
| [docs/provider-interfaces.md](docs/provider-interfaces.md) | Ports |
| [docs/data-model.md](docs/data-model.md) | PostgreSQL conceptual schema |
| [docs/api-design.md](docs/api-design.md) | REST / session establishment |
| [docs/tools-design.md](docs/tools-design.md) | Tools / MCP |
| [docs/rag-design.md](docs/rag-design.md) | Knowledge |
| [docs/memory-design.md](docs/memory-design.md) | Memory kinds |
| [docs/workflow-design.md](docs/workflow-design.md) | Graphs vs agents |
| [docs/multi-agent-design.md](docs/multi-agent-design.md) | Handoff |
| [docs/security.md](docs/security.md) | Authz, isolation, injection |
| [docs/observability.md](docs/observability.md) | OTel, metrics |
| [docs/evaluation.md](docs/evaluation.md) | Eval + simulation |
| [docs/deployment.md](docs/deployment.md) | Compose, channels |
| [docs/ui-system.md](docs/ui-system.md) | Screens, IA, design language |
| [docs/roadmap.md](docs/roadmap.md) | P1 → vision |
| [docs/integration-guide.md](docs/integration-guide.md) | Two-engineer integration |
| [docs/work-allocation.md](docs/work-allocation.md) | Saif / partner / git |
| [docs/prototype-1.md](docs/prototype-1.md) | P1 cut line |
| [docs/definition-of-done.md](docs/definition-of-done.md) | DoD |
| [docs/decisions/](docs/decisions/) | ADRs |
| [docs/status/phase-0-review.md](docs/status/phase-0-review.md) | Phase 0 audit |
| [docs/status/phase-1-step-1.md](docs/status/phase-1-step-1.md) | Contracts foundation |
| [docs/status/phase-1-step-2.md](docs/status/phase-1-step-2.md) | API + Postgres + Agent CRUD |
| [docs/status/phase-3-step-8.md](docs/status/phase-3-step-8.md) | Final Phase 3 integration and hardening |

---

## Contribution workflow

Described in [docs/work-allocation.md](docs/work-allocation.md). Short-lived branches, conventional commits, contracts on `main` frequently.

---

## License

TBD (not set in Phase 0).
