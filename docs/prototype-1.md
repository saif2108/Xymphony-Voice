# Prototype 1 — Precise Cut Line

**Horizon:** NOW · **Duration assumption:** ~7–14 working days, two engineers, heavy AI coding assistance.  
**Goal:** *Create an agent and talk to it in realtime.*  
**Not implemented in-repo as of Phase 0.**

Master architecture: [architecture.md](architecture.md). Requirements: [requirements.md](requirements.md). Runtime: [runtime-design.md](runtime-design.md). Split: [work-allocation.md](work-allocation.md).

---

## 1. What Prototype 1 is

A **vertical slice** of the platform:

1. Authenticated (or documented local-dev auth) user in an Organization/Project  
2. Create and save an Agent + draft AgentVersion  
3. Configure instructions  
4. Select LLM (from a registry of adapters; at least one live adapter)  
5. Select TTS voice (at least one live adapter)  
6. Select STT (at least one live adapter; may share vendor with others)  
7. Launch Playground  
8. Microphone → WebRTC → LiveKit → VAD → STT → Runtime → LLM → TTS → speakers  
9. Interruption / barge-in  
10. Live transcript  
11. Basic session metadata persisted  
12. Agent configuration persisted so a refresh can reload it  

**Architectural obligation:** even with **one** live adapter per port, the runtime talks to **ports**, not vendor SDKs directly. A second LLM adapter may be a stub that fails closed — but the interface exists.

---

## 2. Pipeline (P1 only)

```
Browser
  → WebRTC
  → LiveKit
  → Realtime Session
      ├── VAD / turn detection
      ├── STT
      ├── Xymphony Agent Runtime
      │     └── LLM   (no tools, no RAG, no workflow)
      └── TTS
  → Audio back to user
```

---

## 3. Acceptance criteria

Must all pass before calling P1 “done”:

| # | Criterion | Evidence |
| --- | --- | --- |
| 1 | Create agent with name + instructions, save, reload dashboard, still there | Manual + API test |
| 2 | Choose LLM and TTS from UI lists backed by adapter registry | UI + registry test |
| 3 | Start playground; grant mic; connection reaches runtime worker | Logs: session_id |
| 4 | User speech appears as streaming/final transcript | UI |
| 5 | Agent audio plays; multi-turn works (≥3 turns) | Manual + realtime test |
| 6 | Barge-in: during agent speech, user speaks → TTS stops quickly; no “two voices”; next answer uses the new user utterance | Realtime test + NFR-REL-001 |
| 7 | In-flight LLM cancelled on barge-in; late tokens do not speak | Unit + realtime |
| 8 | Session row stored with agent_version_id, timestamps, status | DB/API |
| 9 | Transcript messages stored | API GET |
| 10 | Provider timeout surfaces Error in UI and does not freeze mic | Fault injection |
| 11 | Org/project id on session; no cross-tenant IDs in snapshot | Code review + test |
| 12 | Secrets not in git, not in client bundle, not in version JSON | Review |
| 13 | OTel spans (or structured JSON traces) for STT, LLM, TTS | Logs |
| 14 | README can start Compose (when Phase 1 adds it) and reach playground | Docs |

Definition of done extras: [definition-of-done.md](definition-of-done.md).

---

## 4. Explicitly NOT in Prototype 1

- Knowledge upload, chunking, pgvector retrieval  
- Tools, webhooks, MCP, Python UDF  
- Workflow editor / LangGraph product surface  
- Session inspector beyond transcript + status  
- Analytics dashboards  
- Multiple production-ready providers (stubs OK)  
- Publish/rollback/shadow deployments  
- Memory (long-term / user)  
- Multi-agent, HITL  
- Evaluation, simulation  
- Telephony  
- SDK  
- Fine-grained RBAC  
- Recordings  
- Describe-your-agent / talk-to-build  
- Kubernetes  
- Separate `apps/playground` package  

**STT in P1:** required (not “LLM audio in/out only”), because the platform’s STT port must be proven. Using a realtime speech-to-speech vendor **as a bypass of STT+LLM+TTS ports** is **rejected** for P1 (it would skip our runtime). A vendor that exposes separate STT/LLM/TTS APIs is fine.

---

## 5. Suggested defaults (P1)

These are **starting adapters**, not core identity:

| Port | First adapter (assumption) | Fallback |
| --- | --- | --- |
| LLM | OpenAI-compatible (`LLMProvider`) | Anthropic or Ollama if keys dictate |
| STT | AssemblyAI streaming **or** Deepgram **or** Whisper-live if latency allows | Document measured latency |
| TTS | ElevenLabs **or** Cartesia | Piper local if offline demo needed |
| Media | LiveKit Cloud **or** self-hosted LiveKit in Compose | — |

Exact vendor enabled in the first PR is an unresolved credential decision; the **ports are not**. See [status/phase-0-review.md](status/phase-0-review.md).

**VAD:** LiveKit / Silero VAD via runtime, not a hardcoded SaaS.

---

## 6. Auth scope (P1)

Minimum: prevent anonymous control-plane writes; stamp `organization_id` / `project_id` on all rows.

Acceptable P1 implementations (pick one in Phase 1, document in an ADR):

- A. First-party email/password or magic link + HTTP-only session  
- B. Hosted IdP (Clerk/Auth0) behind an `IdentityProvider` port  

**Not acceptable:** hardcoded global agent with no tenancy columns “to save time.”

---

## 7. Data persisted (P1)

- organizations, users, memberships (even if one of each)  
- projects  
- agents, agent_versions (draft)  
- provider_configs (encrypted credentials)  
- sessions, turns, messages (text)  
- optional: event JSON for interrupts (recommended)

**Not P1:** chunks, workflows, eval tables (may exist as unused migrations only if they do not delay P1 — prefer delay).

---

## 8. Feasibility (Phase 0 audit)

| Risk | Mitigation |
| --- | --- |
| LiveKit + Python worker learning curve | Timebox day 1–2 to empty room + echo; then plug runtime |
| Barge-in races | Fake clock unit tests before live audio |
| Provider latency blows NFR-LAT-001 | Treat NFRs as SLO **targets**; P1 ships with measurement even if p95 misses |
| Two engineers diverge | Daily contract sync; `packages/contracts` first |
| Scope creep (tools “while we’re here”) | This document is the kill switch |

**Verdict:** P1 is feasible in 7–14 days if scope is enforced and adapters stay thin.

---

## 9. Phase 1 implementation order (do not start in Phase 0)

1. Monorepo skeletons + Compose: Postgres, Redis, LiveKit, API hello, dashboard hello  
2. Contracts: Event, Session, AgentVersion P1 subset  
3. Control plane: agent CRUD  
4. Runtime worker: join room, VAD, fake LLM/TTS  
5. Real adapters + interruption  
6. Persistence + playground polish  

See [integration-guide.md](integration-guide.md).
