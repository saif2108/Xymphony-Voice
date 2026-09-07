# Architecture — Xymphony Voice

**Status:** Phase 0 (documentation only). No runtime is implemented in this repository yet.  
**Canonical terms:** [glossary.md](glossary.md)  
**Deeper docs:** [runtime-design.md](runtime-design.md) · [event-model.md](event-model.md) · [data-model.md](data-model.md) · [security.md](security.md) · [deployment.md](deployment.md)

This is the **master architecture document**. Other docs specialize; they must not contradict this file.

---

## 1. What we are building

**Xymphony Voice is a platform for building, deploying, testing, and operating intelligent realtime AI agents.**

It is not:

- a single insurance voice bot
- a thin dashboard over LiveKit Agents + one vendor
- a chatbot with a microphone

It is an **operating platform**: create → configure → teach → connect → test → evaluate → publish → deploy → monitor → improve → version → rollback.

The **product core** is the **Xymphony Agent Runtime**. LiveKit moves audio. Providers generate tokens and waveforms. The runtime owns session, turn, event, state, tools, retrieval, workflows, interruption, cancellation, and observability.

---

## 2. Why this architecture

| Problem | Architectural answer |
| --- | --- |
| Vendor lock-in (one LLM/STT/TTS) | Ports + adapters ([ADR-002](decisions/ADR-002-provider-abstraction.md)) |
| Config edits mutating live calls | Immutable AgentVersion; Deployments bind versions; sessions pin a snapshot ([ADR-006](decisions/ADR-006-control-data-plane.md)) |
| LLM used as source of truth for business ops | Tools, APIs, workflows, policy — LLM reasons, runtime executes |
| “Dashboard → LiveKit → vendor” with no product | Runtime owns the loop; transport is a plugin |
| Two engineers blocking each other | Control plane vs data plane; shared contracts package |
| Realtime races (barge-in, stale tokens) | Event-driven loop, sequence numbers, cancellation tokens ([ADR-004](decisions/ADR-004-event-driven-runtime.md)) |
| Future telephony / multimodal / multi-agent | Modality-neutral Message/ContentPart; Channel; handoff events — not implemented NOW |

**Intentionally not built now:** Kubernetes, microservices mesh, custom WebRTC, custom STT/TTS/LLM, Temporal, 20 provider SDKs, empty package explosion.

**Chosen shape:** modular monolith (FastAPI control plane + runtime worker + ARQ worker + Next.js dashboard) in a monorepo ([ADR-005](decisions/ADR-005-monorepo.md)).

---

## 3. Current repository state vs target

| Horizon | State |
| --- | --- |
| **Current (2026-09-07)** | Empty git repo (`Xymphony-Voice`), remote `origin` = `https://github.com/saif2108/Xymphony-Voice.git`. No apps, no packages, no compose file. |
| **Phase 0 target** | This documentation system. No application code required. |
| **Prototype 1** | Create agent, configure, select LLM + voice, realtime playground with barge-in. See [prototype-1.md](prototype-1.md). |
| **Prototype 2 / Beta / V1 / Vision** | [roadmap.md](roadmap.md) |

There is **no existing insurance POC in this repository**. If a sibling POC exists outside this repo, treat it as **reference only**. Do not copy its application architecture into this platform.

---

## 4. System architecture

```
                         ┌─────────────────────────────────────────┐
                         │           CLIENTS                        │
                         │  Dashboard (Next.js)  ·  Embed (LATER)   │
                         │  Public API / SDK (LATER) · Telephony     │
                         └─────────────┬───────────────┬────────────┘
                                       │ HTTPS         │ WebRTC
                                       ▼               ▼
┌──────────────────────────────────────────┐    ┌─────────────────────┐
│           CONTROL PLANE                  │    │  REALTIME TRANSPORT │
│  apps/api  (FastAPI)                     │    │  LiveKit Server     │
│  Auth, RBAC, CRUD, publish, deploy       │    │  (not our runtime)  │
│  Source of truth: PostgreSQL             │    └──────────┬──────────┘
│  Secrets: encrypted vault + KMS later    │               │
│  Jobs: ARQ workers (ingest, embed, eval) │               ▼
└──────────────────┬───────────────────────┘    ┌─────────────────────┐
                   │ snapshot at session start  │  DATA PLANE         │
                   ▼                            │  runtime worker     │
         AgentVersion + bindings                │  Xymphony Agent     │
         (immutable)                            │  Runtime            │
                                                │  STT / LLM / TTS    │
                                                │  via Provider ports │
                                                └──────────┬──────────┘
                                                           │
                   PostgreSQL ◄── traces/transcripts ──────┤
                   Redis     ◄── ephemeral session ────────┤
                   S3/MinIO  ◄── docs/recordings ──────────┘
```

**Why control plane vs data plane exists**

- Control plane is **highly consistent, low QPS, strongly authorized CRUD**.
- Data plane is **high QPS, latency-sensitive, cancellation-heavy, streaming**.
- Mixing them (e.g. runtime reading live editor rows every token) causes races, accidental prompt changes mid-call, and credential leakage patterns.
- Configuration reaches the runtime as a **resolved snapshot** loaded once at session start (and only replaced on explicit session restart). See §6.

---

## 5. Configuration flow (control → data)

```
USER edits Agent in Dashboard
  → Control plane writes draft AgentVersion (mutable)
  → User Save / Publish
  → AgentVersion becomes published (immutable)
  → Deployment (or Playground) points at version_id
  → Session start: Runtime fetches snapshot by version_id
  → Snapshot copied into session record (config_hash)
  → In-flight session IGNORES later publishes
```

**If configuration changes while a session is active:** nothing in that session changes. The next Session uses the new Deployment pointer. Playground may offer “restart session to pick up changes.”

**Versioning:** Agent (identity) → AgentVersion (snapshot) → Deployment (binding). See [data-model.md](data-model.md).

---

## 6. Realtime pipeline

```
USER MIC
  → Browser capture
  → WebRTC
  → LiveKit
  → Runtime worker subscribed to audio track
  → VAD / turn detection
  → STT adapter (streaming)
  → Event: TranscriptFrame / UserSpeechEnded
  → Agent Runtime (state, policy, optional retrieve/tools/workflow)
  → LLM adapter (streaming tokens)
  → Sentence/chunk aggregator
  → TTS adapter (streaming audio)
  → LiveKit audio track
  → WebRTC
  → USER SPEAKER
```

Interrupt path is specified in [runtime-design.md](runtime-design.md) § Interruption. It is a **first-class state machine**, not “stop talking if mic is loud.”

---

## 7. Agent runtime internals

```
                    ┌────────────────────────────────────────┐
                    │         SESSION CONTROLLER             │
                    │  lifecycle, reconnect, shutdown        │
                    └─────────────────┬──────────────────────┘
                                      │ events
                    ┌─────────────────▼──────────────────────┐
                    │            EVENT LOOP                  │
                    │  ordered by (session_id, sequence)     │
                    │  cancellation tokens per turn          │
                    └─┬────────┬────────┬─────────┬──────────┘
                      │        │        │         │
                 LLM port  Tool exec  Retriever  Workflow
                      │        │        │         │
                 adapters  HTTP/MCP   pgvector   graph step
```

**LLM is not the system.** If a claim requires a side effect or a business fact, the runtime calls a Tool (or a deterministic policy). The model may narrate the tool result; it may not invent the result.

**NOW (P1):** Runtime = VAD + STT + LLM + TTS + interruption + transcript. No tools, no RAG, no workflow graph.

**NEAR:** Tools + RAG + inspector.

**LATER:** Workflows, memory, multi-agent, eval lab wired to runtime traces.

---

## 8. Provider abstraction

```
Runtime ──► LLMProvider        ──► OpenAI | Anthropic | Gemini | Ollama
       ──► STTProvider         ──► AssemblyAI | Whisper | (Deepgram later)
       ──► TTSProvider         ──► ElevenLabs | Cartesia | Piper
       ──► EmbeddingProvider   ──► (chosen adapter)
       ──► VectorStore         ──► pgvector | (replaceable)
       ──► ToolExecutor        ──► HTTP | webhook | MCP | python
       ──► KnowledgeRetriever  ──► RAG pipeline
       ──► MediaTransport      ──► LiveKit adapter
```

Capability negotiation: adapters declare flags (`streaming`, `tool_calling`, `cancellation`, `vision`, …). Routing refuses a model that cannot satisfy the AgentVersion requirements.

Details: [provider-interfaces.md](provider-interfaces.md). Decision: [ADR-002](decisions/ADR-002-provider-abstraction.md).

---

## 9. Data architecture

| Store | Holds | Does not hold |
| --- | --- | --- |
| **PostgreSQL** | Organizations, users, agents, versions, deployments, sessions, messages, tools, knowledge metadata, chunks+embeddings (pgvector), audit, API keys (hashes) | Raw audio blobs, ephemeral cancellation flags |
| **Redis** | Session ephemeral state, pub/sub to UI, rate limit counters, ARQ queue, distributed locks | System of record for agents/config |
| **S3/MinIO** | Source documents, optional recordings, eval datasets, large artifacts | Canonical agent config |

Decision: [ADR-003](decisions/ADR-003-postgres-pgvector.md). Schema: [data-model.md](data-model.md).

---

## 10. Workflow architecture

Workflows are **graphs**, not Agents. AgentVersion **may** reference `workflow_version_id`.

```
AgentVersion
  ├── instructions, providers, tools, knowledge
  └── optional WorkflowVersion
         ├── nodes (LLM, Tool, Condition, Retrieve, Handoff, …)
         └── edges + conditions
Runtime
  └── WorkflowExecutor steps the graph using the same event loop
```

**NOW:** no workflow executor. Leave the `workflow_version_id` column/contract in the conceptual model as nullable.  
Details: [workflow-design.md](workflow-design.md).

Durable/complex orchestration may use **LangGraph** **inside** the WorkflowExecutor, not as the public product model and not as the voice transport. See [ADR-008](decisions/ADR-008-langgraph-scope.md).

---

## 11. Observability

OpenTelemetry is the conceptual standard.

Trace shape:

```
Session
├── Media.In
├── VAD
├── STT
├── Turn
│   ├── Retrieve? 
│   ├── LLM
│   ├── Tool*
│   ├── LLM (after tools)
│   └── TTS
├── Interrupt?
└── Media.Out
```

Hierarchy: Organization → Project → Agent → Version → Deployment → Session → Turn → Event.

Details: [observability.md](observability.md).

---

## 12. Deployment topology

**NOW / NEAR:** Docker Compose on one machine or a small VM:

- `dashboard`
- `api` (control plane)
- `runtime-worker` (joins LiveKit)
- `arq-worker`
- `postgres` + pgvector
- `redis`
- `minio`
- `livekit`
- `caddy`/`nginx` optional

**Not NOW:** Kubernetes. Revisit when a concrete multi-tenant SLA, multi-region, or ops requirement appears ([deployment.md](deployment.md)).

---

## 13. Target repository structure (not created as empty shells)

When Phase 1 starts, create packages **as they gain code**:

```
Xymphony-Voice/
  apps/
    dashboard/          # Next.js control plane UI + playground routes
    api/                # FastAPI control plane
    runtime-worker/     # Data plane process (LiveKit job + agent loop)
  packages/
    contracts/          # Shared types: Agent, Event, Session, errors
    agent-runtime/      # The product
    realtime/           # Transport adapters (LiveKit)
    providers/          # LLM/STT/TTS/embedding adapters
    tools/              # ToolExecutor implementations (NEAR)
    rag/                # Ingest + retrieve (NEAR)
    workflows/          # Graph executor (LATER)
    memory/             # (LATER)
    evaluation/         # (LATER)
    observability/      # OTel helpers
  infrastructure/
    docker/
  tests/
    unit/ integration/ realtime/ evaluation/ e2e/
  docs/                 # This Phase 0 set
```

**P1 note:** `apps/playground` is **not** a separate app. Playground is a dashboard route to keep the two-engineer surface small. Split later if embeddable playground becomes a product.

**Do not** add a package until it has a module and a test. Contracts + agent-runtime + providers + realtime + api + dashboard are the P1 set.

---

## 14. Shared contracts ownership

`packages/contracts` is the compatibility boundary between:

- FastAPI (serialization)
- Runtime worker (execution)
- Dashboard (TypeScript types generated from JSON Schema or OpenAPI)

**Rule:** runtime must not import dashboard. Dashboard must not import runtime internals. Both may import contracts (TS generated from the Python/JSON schemas).

Conceptual modules (implementation waits): `agent`, `events`, `sessions`, `providers`, `tools`, `workflows`, `deployments`.

Version contracts with `schema_version` on events and OpenAPI `/v1`.

---

## 15. Failure, scale, test, replace

| Concern | Decision |
| --- | --- |
| **Failure** | Timeouts per provider (defaults in runtime-design). Cancel turn on barge-in. LLM timeout → Error event + user-safe audio/text. Tool timeout → ToolResult error, model may retry if policy allows. Postgres down → control plane 503; data plane continues existing sessions until snapshot/trace flush fails (then degrade: keep talking, queue traces). Redis down → lose ephemeral UI pub/sub and rate limits; sessions that already hold state in-process continue. LiveKit disconnect → reconnect policy then terminate. |
| **Scale** | Horizontal runtime workers (LiveKit job dispatch). Control plane stateless. Postgres primary. Redis for hot keys. No Kafka NOW. |
| **Test** | pytest for runtime/state machines with fake providers; Playwright for dashboard; realtime tests with recorded audio fixtures; load tests LATER. [definition-of-done.md](definition-of-done.md) |
| **Replace** | Swap adapter implementing the port. Swap VectorStore interface. Swap LiveKit only behind MediaTransport (expensive; not planned). |

---

## 16. Security (summary)

Defense in depth: org/project isolation on every query, RBAC on control plane, hashed API keys, encrypted provider secrets, tool allowlists + SSRF guards, prompt-injection treated as expected input, transcripts classified, retention jobs. Full mechanisms: [security.md](security.md).

---

## 17. Traceability example

`FR-VOICE-001` (realtime voice conversation) → Agent Runtime + LiveKit transport → `sessions` table → `POST /v1/sessions` + LiveKit token → Playground → `tests/realtime/test_barge_in.py`.

Full map: [requirements.md](requirements.md).

---

## 18. What we are not building (Phase 0 / P1)

Kubernetes, telephony/SIP, custom WebRTC, marketplace, multi-region active-active, LangGraph as the public UX, insurance-domain logic, hardcoded single-vendor pipeline, hidden CoT in the Live Agent Brain UI.

---

## 19. Deferred decisions

Listed in [status/phase-0-review.md](status/phase-0-review.md). Highest impact: identity vendor vs first-party auth for P1; exact STT/TTS vendors enabled on day one (adapters exist as interfaces regardless).

---

## 20. Related documents

| Doc | Role |
| --- | --- |
| [product-spec.md](product-spec.md) | Who and why |
| [runtime-design.md](runtime-design.md) | How the loop works |
| [event-model.md](event-model.md) | Event envelope |
| [prototype-1.md](prototype-1.md) | Exact P1 cut line |
| [work-allocation.md](work-allocation.md) | Two-engineer split |
