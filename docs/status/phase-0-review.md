# Phase 0 Review

**Date:** 2026-09-07  
**Determination:** **Phase 0 COMPLETE** (documentation foundation). **Phase 1 not started.**  
**Repository at start:** empty git clone of `https://github.com/saif2108/Xymphony-Voice.git` (nested at `Xymphony-Voice/`). No application source, no Compose, no packages.

This file records what Phase 0 produced and the audits required by the Phase 0 charter.

---

## 1. What was created

All paths relative to `Xymphony-Voice/`:

| Path | Role |
| --- | --- |
| `README.md` | Engineer onboarding; honest “no code yet” |
| `CLAUDE.md` | Binding rules for AI/human implementers |
| `.gitignore` | Engineering hygiene (not an app) |
| `docs/glossary.md` | Canonical vocabulary |
| `docs/architecture.md` | Master architecture |
| `docs/requirements.md` | FR/NFR IDs + traceability |
| `docs/product-spec.md` | Product, personas, journey, tiers |
| `docs/prototype-1.md` | Exact P1 cut line |
| `docs/runtime-design.md` | Loop, barge-in, latency, failure |
| `docs/event-model.md` | Envelope, catalog, persist policy |
| `docs/provider-interfaces.md` | Ports |
| `docs/data-model.md` | Conceptual Postgres |
| `docs/api-design.md` | `/v1` control plane |
| `docs/tools-design.md` | Tools/MCP (NEAR) |
| `docs/rag-design.md` | Knowledge (NEAR) |
| `docs/memory-design.md` | Six memory kinds |
| `docs/workflow-design.md` | Graphs ≠ agents |
| `docs/multi-agent-design.md` | Handoff (LATER) |
| `docs/security.md` | Mechanisms |
| `docs/observability.md` | OTel hierarchy |
| `docs/evaluation.md` | Eval + simulation |
| `docs/deployment.md` | Compose, channels |
| `docs/ui-system.md` | IA + screens |
| `docs/roadmap.md` | Horizons |
| `docs/integration-guide.md` | Handshake + milestones |
| `docs/work-allocation.md` | Two-engineer + git |
| `docs/definition-of-done.md` | DoD |
| `docs/decisions/ADR-001` … `ADR-008` | Architecture decisions |
| `docs/status/saif.md` | Engineer A log |
| `docs/status/partner.md` | Engineer B log |
| `docs/status/phase-0-review.md` | This file |

Extra vs the original file list (justified): `glossary.md`, `prototype-1.md`, `tools-design.md`, `definition-of-done.md`, `ADR-007`, `ADR-008`, `.gitignore`. These prevent vocabulary drift, P1 scope creep, undocumented job/LangGraph choices.

**Not created:** empty `apps/` / `packages/` trees, `docker-compose.yml`, `pyproject.toml`, application code.

---

## 2. What was modified

**Before Phase 0:** no tracked project files (only `.git`).

**Modified after first write (consistency fixes):**

- `docs/glossary.md` — Session status does not include `interrupted`  
- `docs/runtime-design.md` — Session state machine aligned  
- `docs/integration-guide.md` — who writes session vs turns  
- `docs/data-model.md` — same write-path  

---

## 3. Architecture decisions (summary)

| ADR | Decision |
| --- | --- |
| 001 | LiveKit = MediaTransport, not the runtime |
| 002 | Ports/adapters; no vendor core |
| 003 | Postgres + pgvector initially |
| 004 | In-process event loop; no Kafka |
| 005 | Monorepo; packages only when they have code |
| 006 | Control vs data plane; snapshot pinning |
| 007 | ARQ + Redis for jobs (not P1) |
| 008 | LangGraph only inside workflow executor later |

Additional locked choices without separate ADRs:

- Modular monolith: FastAPI + runtime-worker + Next.js  
- Playground is a dashboard route  
- Workspace = UX of Organization; no `workspaces` table NOW  
- LLM is not system of record for side effects  
- P1 STT+LLM+TTS ports required (no speech-to-speech bypass of the runtime)

---

## 4. Assumptions

1. Two full-time engineers + heavy AI coding assistance.  
2. Calendar ranges are planning assumptions, not commitments.  
3. No insurance POC exists **in this repo**; any external POC is reference only.  
4. P1 auth may be first-party or hosted IdP behind a port.  
5. First live adapters depend on which API keys the team has; ports do not.  
6. Latency NFRs are **targets to measure**; P1 can ship if measured and barge-in is correct even if p95 misses.  
7. License for the repo is TBD.  
8. Default numeric timeouts/TTLs in runtime-design are **proposed defaults**, tuned after traces exist.  
9. English-first P1; `locale` exists on AgentVersion for later.  
10. Single region P1.

---

## 5. Unresolved decisions (do not block Phase 0; resolve in Phase 1 week 1)

| ID | Topic | Options | Default if we must start |
| --- | --- | --- | --- |
| U-001 | Identity | First-party vs Clerk/Auth0 | First-party email/password for speed of self-host story |
| U-002 | First LLM adapter | OpenAI-compatible vs Anthropic vs Ollama | OpenAI-compatible API (covers many gateways) |
| U-003 | First STT | AssemblyAI vs Deepgram vs other | Whichever key exists; measure TTFA |
| U-004 | First TTS | ElevenLabs vs Cartesia vs Piper | ElevenLabs if key else Piper for offline |
| U-005 | LiveKit Cloud vs Compose LiveKit | Cloud vs OSS | Compose OSS for local; Cloud optional |
| U-006 | Python monorepo tool | uv vs poetry | **uv** (fast, modern) — pick on first `pyproject.toml` |
| U-007 | Exact E2E latency SLO after measurement | keep 800/1800 or relax | Keep as target |
| U-008 | Open source license | MIT vs other | TBD by owners |
| U-009 | RLS in Postgres NOW vs later | enable RLS NEAR | App-level filters P1; RLS NEAR |

---

## 6. Risks

| Risk | Severity | Mitigation |
| --- | --- | --- |
| Scope creep (tools/RAG in P1) | High | prototype-1.md kill switch; CLAUDE.md |
| Barge-in races | High | Unit tests before live audio |
| LiveKit learning curve | Medium | M2 echo milestone |
| Provider latency | Medium | Measure; chunk TTS |
| Accidental LiveKit-Agents-as-architecture | High | ADR-001 + CLAUDE.md |
| Secret leakage via logs/UI | High | security.md; no keys in version JSON |
| Two-engineer contract drift | High | Daily snapshot JSON; short branches |
| Empty-repo rust until Phase 1 | Low | Docs are the artifact |

---

## 7. Contradictions found and resolved

| Issue | Resolution |
| --- | --- |
| Session `interrupted` vs turn-level interrupt | Session stays `active`; Turn `cancelled`; Message `interrupted` |
| Who inserts `sessions` | Control plane POST creates row; worker updates + inserts child rows |
| `apps/playground` vs dashboard route | Dashboard route for P1 |
| Workspace as table vs UX | UX only NOW |
| “One process for P1” temptation | Default two processes; ADR-006 |

---

## 8. Intentionally deferred

Kubernetes; telephony; custom WebRTC; tools/RAG/workflows/MCP; eval lab; multi-agent; HITL; SDK; RBAC beyond owner; recordings; describe-your-agent; talk-to-build; model routing; LangGraph; ARQ worker; MinIO; empty package directories; all Tier 2/3 features as P1 work.

---

## 9. Prototype 1 readiness

**Ready to implement.** Cut line is specific: create/save agent, select LLM+STT+TTS via registry, playground voice, barge-in, transcript, session metadata, tenancy columns, secrets not in client, OTel/JSON traces.

**Not ready to claim P1 done** — no code.

Feasibility: **yes** in 7–14 days if scope holds.

---

## 10. Implementation prerequisites (before first feature PR)

1. Agree U-001–U-006 enough to not thrash week 1.  
2. Obtain LiveKit (local or cloud) + at least one LLM + STT + TTS credential (or Piper + local STT for a degraded path).  
3. Create monorepo skeletons on `main` (Compose, API health, dashboard hello, contracts package).  
4. Freeze P1 AgentVersion JSON + Event envelope in code matching docs.

---

## 11. Phase 1 prerequisites (exit Phase 0 → enter implementation)

- [x] P1 defined  
- [x] Audio path drawn  
- [x] Agent / Version / Deployment / Session / Turn / Event defined  
- [x] Provider replaceability  
- [x] Two-engineer split  
- [x] Module boundaries  
- [x] CLAUDE.md  
- [x] First screens + design language  
- [x] Interruption + cancellation specified  
- [x] Tools/RAG/workflows/eval/observability designed for later  
- [x] P1 exclusions listed  
- [ ] **Not in Phase 0:** running software  

---

## 12. Architecture changes recommended **before** implementation

None that reopen Phase 0. Small Phase 1 choices only (U-001–U-006).

Optional tightening (not blockers):

- Add JSON Schema files for Event and AgentVersion **as the first Phase 1 commit** (contracts in code).  
- Prefer **uv** without another ADR unless someone objects.  

**Do not** add Kubernetes, a message broker, or tools “to be future-proof” in P1.

---

## 13. Documentation completeness (charter checklist)

| # | Question | Answer |
| --- | --- | --- |
| 1 | P1 exact? | Yes — prototype-1.md |
| 2 | Packet → agent → user? | architecture.md + runtime-design.md |
| 3–8 | Agent…Event? | glossary + data-model |
| 9–12 | Replace LLM/STT/TTS/vector? | provider-interfaces + ADRs |
| 13–14 | Parallel + boundaries? | work-allocation + CLAUDE.md |
| 15 | Claude context? | CLAUDE.md + docs |
| 16–17 | Screens + language? | ui-system.md |
| 18–19 | Interrupt/cancel? | runtime-design.md |
| 20–24 | Tools/RAG/workflows/versioning/eval? | respective docs |
| 25 | Observability? | observability.md |
| 26–27 | P1 non-goals? | prototype-1 + requirements NR-* |
| 28 | New engineer? | README index |
| 29 | Implement without major ambiguity? | Yes, remaining = U-001–U-009 |

---

## 14. Security / realtime / provider / scale / parallel audits (short)

**Security:** Tenancy on every table, secrets vault, tool SSRF later, injection assumed, P1 minimum auth+isolation+encrypted keys. Gap: IdP not chosen (U-001). RLS deferred NEAR.

**Realtime failure:** Timeouts, ignore stale events, provider fail-turn, LiveKit disconnect, SIGTERM drain. Gap: P1 no session resume (accepted).

**Provider:** Ports + capabilities + fakes. Gap: first vendors (U-002–004).

**Scale:** Horizontal workers later; Compose P1; no Kafka. Gap: none for P1.

**Parallel:** Unblocked after M0 + contracts. Shared: event envelope, snapshot JSON, LiveKit token API.

---

## 15. Phase 0 COMPLETE / NOT COMPLETE

**Phase 0 COMPLETE.**

Evidence: the files in §1 exist, cross-link, share glossary terms, distinguish current vs P1 vs later, and forbid starting Phase 1 in CLAUDE.md/README. No application code was added, matching the charter.
