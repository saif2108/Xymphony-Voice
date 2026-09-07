# CLAUDE.md — Instructions for AI coding agents

You are implementing **Xymphony Voice**, a **platform** for building, deploying, testing, and operating **intelligent realtime AI agents**.

This is **not** an insurance chatbot. This is **not** a demo that hardcodes one LLM, one STT, and one TTS. This is **not** “Dashboard → LiveKit → vendor.”

The **product core** is the **Xymphony Agent Runtime**. LiveKit is media transport. Vendors are adapters.

Read **[docs/glossary.md](docs/glossary.md)** before naming anything. Canonical terms: Agent, AgentVersion, Deployment, Session, Turn, Message, Event, Tool, Workflow, KnowledgeSource, Document, Memory (six kinds), Provider, Project, Workspace (UX of Organization).

---

## Current phase

**Phase 1 Step 2:** control-plane API + Postgres + Agent CRUD.

- Do **not** implement LiveKit, STT/LLM/TTS adapters, the dashboard, or the agent runtime in this step.
- Do **not** add tools, RAG, memory, workflows, or multi-agent execution.
- Shared contracts: `packages/contracts`. API: `apps/api`.
- When implementing later Prototype 1 slices, follow **[docs/prototype-1.md](docs/prototype-1.md)** only.

Nothing is implemented until code and tests exist. **Do not claim a feature is implemented if it is only documented.**

Contracts source of truth in code: `packages/contracts` (`xymphony_contracts`). Docs remain normative; if code and docs diverge, fix the smaller side and record it in `docs/status/`.

---

## Architecture (mandatory)

Master: [docs/architecture.md](docs/architecture.md)

- **Control plane** (`apps/api` + dashboard): config, auth, CRUD. PostgreSQL is source of truth.  
- **Data plane** (`apps/runtime-worker` + `packages/agent-runtime`): sessions, audio, inference, cancellation.  
- Sessions pin an **immutable AgentVersion snapshot**. Editing the builder does **not** mutate in-flight sessions.  
- **Event-driven** loop: [docs/event-model.md](docs/event-model.md), [docs/runtime-design.md](docs/runtime-design.md).  
- **LLM is not the system of record.** Side effects and business facts go through **tools** (when they exist).  
- **Ports, not vendors** in the runtime: [docs/provider-interfaces.md](docs/provider-interfaces.md), [docs/decisions/ADR-002-provider-abstraction.md](docs/decisions/ADR-002-provider-abstraction.md).

**Do not implement a feature by bypassing an existing architectural abstraction simply because doing so is faster.**

**Before making a major architectural change, inspect `docs/decisions` and existing contracts.**

If you need a new decision, add an ADR. Update glossary if terms change. Update this file if rules change.

---

## Module boundaries

| Package / app | May import | Must not import |
| --- | --- | --- |
| `packages/contracts` | stdlib, pydantic | vendors, FastAPI, React |
| `packages/agent-runtime` | contracts, provider **ports** | dashboard, vendor SDKs |
| `packages/providers` | contracts, vendor SDKs | dashboard |
| `packages/realtime` | contracts, LiveKit SDK | dashboard |
| `apps/api` | contracts, db | LiveKit media loop, React |
| `apps/dashboard` | generated API types, LiveKit **client** | Python runtime internals, provider secret values |
| `apps/runtime-worker` | runtime, realtime, providers, contracts | Next.js |

Do not put business logic in UI. Do not put CSS in the worker.

**Do not create empty packages** to decorate the tree. Create a package when it has code and tests.

Playground is a **dashboard route**, not `apps/playground`, unless an ADR says otherwise.

---

## Coding rules

- Typed interfaces everywhere (Pydantic models, TypeScript types).  
- Small files; split before 800–1000 lines.  
- No giant god-modules (`runtime.py` doing HTTP + VAD + UI).  
- No unnecessary dependencies. Justify new libraries in the PR.  
- No speculative Kubernetes, Kafka, or extra databases.  
- No hidden architecture changes in “drive-by” refactors.  
- Preserve event envelope field names; additive optional fields only.  
- Maintain backwards compatibility of persisted `schema_version` where appropriate.  
- Ask before destructive changes (drop tables, rewrite contracts, delete docs).  
- Do not rewrite unrelated files.  
- Prefer a modular monolith as documented.  

Python: FastAPI, Pydantic v2, asyncio.  
Frontend: Next.js, React, TypeScript, Tailwind, shadcn/ui.

---

## Provider rules

- No `if provider == "openai"` in `agent-runtime`.  
- Adapters declare **capabilities**. Fail closed if the snapshot requires a missing capability.  
- Fakes (`FakeLLM`, `FakeSTT`, `FakeTTS`) are first-class for tests.  
- P1 may have **one** live adapter per port; the **port** still exists.

---

## Security rules

- Never commit secrets. Never log secrets, raw audio PCM, or provider keys.  
- Never send provider keys to the browser.  
- Every query is tenant-scoped (`organization_id`, `project_id`).  
- Treat user speech and retrieved documents as untrusted (prompt injection).  
- Tool HTTP: SSRF controls when tools exist ([docs/security.md](docs/security.md)).  
- Published AgentVersions are immutable.

---

## Observability and errors

- JSON logs with `session_id`, `turn_id`, `correlation_id`.  
- OpenTelemetry spans on session/turn/stt/llm/tts/interrupt.  
- Timeouts as specified in [docs/runtime-design.md](docs/runtime-design.md); do not deadlock the loop.  
- Provider failures emit `Error` events and user-safe fallback; do not crash the worker process for one session.

---

## Realtime rules

- Barge-in: cancel TTS + LLM; drop stale events; persist **played** assistant text only.  
- Sequence numbers from the session loop.  
- Do not use timestamp ordering as the source of truth.  
- Do not resume cancelled turn audio in P1 (simpler).  

---

## Testing rules

Follow [docs/definition-of-done.md](docs/definition-of-done.md).

- pytest for backend/runtime.  
- Playwright for dashboard e2e when UI exists.  
- Realtime: interruption, cancellation, multi-turn, provider failure, stale events.  
- **Test before claiming completion.**  
- Do not delete tests to make CI green.

---

## Documentation rules

- Architecture change → update the relevant `docs/*.md` in the same PR.  
- Do not invent implemented functionality in README.  
- Horizons: NOW / NEAR / LATER / VISION — do not promote VISION into P1 tickets.

---

## Git

- Conventional commits. Feature branches short-lived. No force-push `main`.  
- See [docs/work-allocation.md](docs/work-allocation.md).

---

## If you are unsure

1. Glossary  
2. `docs/prototype-1.md` for scope  
3. ADRs  
4. Ask the user rather than silently expanding scope
