# Requirements

**Status:** Phase 0. Requirements are contractual for planning; they are **not** implemented.  
**IDs** are stable. Horizon: **NOW** = Prototype 1, **NEAR** = Prototype 2, **LATER** = Beta/V1, **VISION** = beyond V1.

Canonical terms: [glossary.md](glossary.md). Product narrative: [product-spec.md](product-spec.md). Architecture map: [architecture.md](architecture.md).

Traceability columns: **Arch** = component, **Data** = entities, **API**, **UI**, **Runtime**, **Test**.

---

## 1. Functional requirements

### 1.1 Agents and configuration

| ID | Req | Horizon | Arch | Data | API | UI | Runtime | Test |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| FR-AGT-001 | User can create an Agent in a Project | NOW | Control plane | agents | POST /agents | Agent list/builder | Loads version at session | API + e2e |
| FR-AGT-002 | User can set display name, description | NOW | Control plane | agents | PATCH /agents | Builder | — | API |
| FR-AGT-003 | User can edit system instructions / personality on a draft version | NOW | Control plane | agent_versions | PATCH /agent-versions | Config | Injects as system prompt | API + playground |
| FR-AGT-004 | User can select LLM provider + model for a version | NOW | Providers | agent_versions.model | PATCH | Config | LLM port | Contract test per adapter |
| FR-AGT-005 | User can select TTS provider + voice | NOW | Providers | agent_versions.tts | PATCH | Voice studio | TTS port | Adapter test |
| FR-AGT-006 | User can select STT provider | NOW | Providers | agent_versions.stt | PATCH | Config | STT port | Adapter test |
| FR-AGT-007 | User can save a draft AgentVersion | NOW | Control plane | agent_versions | POST/PATCH | Builder | — | API |
| FR-AGT-008 | User can list agents in a Project | NOW | Control plane | agents | GET /agents | Agent list | — | API |
| FR-AGT-009 | Publish creates an immutable AgentVersion | NEAR | Versioning | agent_versions.status | POST …/publish | Version history | Sessions pin version_id | API |
| FR-AGT-010 | Rollback Deployment to a previous published version | LATER | Deployments | deployments | POST …/rollback | Version history | New sessions only | API |
| FR-AGT-011 | Goals, constraints, language, guardrails as structured fields | NEAR | Agent model | agent_versions | PATCH | Config | Policy + prompt compiler | Unit |
| FR-AGT-012 | Describe-your-agent generates a draft version for review | LATER | Builder agent | draft version | POST …/generate | Builder | Builder is not prod runtime | Eval |

### 1.2 Realtime voice

| ID | Req | Horizon | Arch | Data | API | UI | Runtime | Test |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| FR-VOICE-001 | User can start a playground Session with microphone | NOW | Runtime + LiveKit | sessions | POST /sessions + token | Playground | Full pipeline | Realtime |
| FR-VOICE-002 | Streaming STT produces transcript events | NOW | STT port | messages/events | WS/events | Playground | STT adapter | Fake STT |
| FR-VOICE-003 | Streaming LLM + TTS; user hears audio | NOW | LLM/TTS ports | — | media | Playground | Loop | Realtime |
| FR-VOICE-004 | Barge-in: user speech cancels TTS and in-flight LLM | NOW | Cancellation | events | — | Playground | Interrupt FSM | Realtime barge-in |
| FR-VOICE-005 | Multi-turn conversation in one Session | NOW | Session | turns, messages | — | Playground | Turn machine | Realtime |
| FR-VOICE-006 | Session shows live transcript | NOW | Events → UI | messages | event stream | Playground | Emit TranscriptFrame | e2e |
| FR-VOICE-007 | Text complementary channel in same Session model | NEAR | ContentPart | messages | POST …/messages | Playground | TextFrame path | Integration |
| FR-VOICE-008 | Reconnect within TTL resumes same Session media | LATER | Session | sessions | token refresh | Playground | Resume policy | Realtime |
| FR-VOICE-009 | Telephony/SIP channel | VISION | Channel | deployments.channel | — | — | Same runtime, different transport | — |

### 1.3 Tools, knowledge, workflows

| ID | Req | Horizon | Arch | Data | API | UI | Runtime | Test |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| FR-TOOL-001 | Define Tool with JSON schema, timeout, permissions | NEAR | tools | tools, tool_versions | /tools | Tools | ToolExecutor | Unit + contract |
| FR-TOOL-002 | AgentVersion binds an allowlist of tools | NEAR | AgentVersion | bindings | PATCH | Builder | Refusal if not bound | Integration |
| FR-TOOL-003 | LLM proposes tool call; runtime executes; result returned | NEAR | Runtime | events | — | Brain | ToolCall/ToolResult | Integration |
| FR-TOOL-004 | MCP server as a Tool source | NEAR | tools | tools.kind=mcp | /tools | Tools | MCP adapter | Integration |
| FR-TOOL-005 | Webhook/REST tools with SSRF protections | NEAR | tools | — | — | — | HTTP executor | Security tests |
| FR-RAG-001 | Upload document to KnowledgeSource | NEAR | RAG | knowledge_*, object store | /knowledge | Knowledge | — | Integration |
| FR-RAG-002 | Ingest: parse, chunk, embed, store | NEAR | ARQ + RAG | chunks | job | Knowledge | Retriever | Integration |
| FR-RAG-003 | Retrieve + inject context on turn | NEAR | Retriever | — | — | Brain | Retrieve span | Eval retrieval |
| FR-RAG-004 | Citations in inspector | NEAR | Events | events.metadata | — | Inspector | RetrievalResult | e2e |
| FR-WF-001 | Visual workflow editor (React Flow) | LATER | workflows | workflow_versions | /workflows | Workflow builder | — | e2e |
| FR-WF-002 | Runtime steps published WorkflowVersion | LATER | WorkflowExecutor | — | — | Brain | Graph | Integration |
| FR-WF-003 | Human handoff and agent handoff nodes | LATER | HITL / multi-agent | — | — | Mission control | Handoff events | Integration |

### 1.4 Sessions, inspect, evaluate

| ID | Req | Horizon | Arch | Data | API | UI | Runtime | Test |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| FR-SES-001 | Persist session metadata (ids, version, status, timestamps) | NOW | Data | sessions | GET /sessions/:id | Playground | Write on start/end | API |
| FR-SES-002 | Persist transcript messages | NOW | Data | messages | GET …/messages | Playground | Commit on turn | API |
| FR-SES-003 | Session inspector: structured events, not hidden CoT | NEAR | Events | events | GET …/events | Inspector | Persist selected types | e2e |
| FR-SES-004 | Conversation replay (text + optional audio) | LATER | Object store | recordings | — | Replay | Optional record | e2e |
| FR-EVAL-001 | Evaluation dataset + scenarios | LATER | evaluation | evaluations | /evaluations | Evaluation | Offline runner | Eval tests |
| FR-EVAL-002 | Simulation lab (AI user) | LATER | simulation | scenarios | /simulations | Sim lab | Dual runtime | Eval |
| FR-AN-001 | Analytics: sessions, latency, cost, errors | NEAR | OTel + rollups | metrics | /analytics | Analytics | Emit metrics | — |

### 1.5 Security, tenancy, ops

| ID | Req | Horizon | Arch | Data | API | UI | Runtime | Test |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| FR-SEC-001 | Authenticated users only for control plane | NOW | Auth | users | /auth | Sign-in | Worker uses service creds | e2e |
| FR-SEC-002 | Organization + Project isolation on all queries | NOW | Tenancy | *_organization_id | — | — | Snapshot includes org | Security tests |
| FR-SEC-003 | RBAC (Owner/Admin/Developer/Viewer) | LATER | RBAC | memberships | — | Settings | — | Authz tests |
| FR-SEC-004 | Provider credentials stored encrypted, never in AgentVersion plaintext logs | NOW | Secrets | provider_configs | Settings | Settings | Hydrate at session | Security |
| FR-SEC-005 | API keys hashed, scoped to Project | LATER | API keys | api_keys | /api-keys | Settings | — | Authn |
| FR-SEC-006 | Audit log for config and tool side effects | LATER | Audit | audit_logs | — | Settings | Tool executor | — |
| FR-OBS-001 | Structured logs + traces per Session/Turn | NOW | OTel | — | — | — | Spans | Unit (span names) |

---

## 2. Non-functional requirements

| ID | Req | Target | Horizon | Notes |
| --- | --- | --- | --- | --- |
| NFR-LAT-001 | E2E speech-end → first agent audio | p50 **< 800ms**, p95 **< 1800ms** in playground, same region as providers | NOW measure; tune NEAR | Proposed defaults; actuals depend on vendor. Track even if missed. |
| NFR-LAT-002 | LLM TTFT | p50 < 400ms for P1 default model class | NOW | Adapter-dependent |
| NFR-LAT-003 | TTS TTFB after first speakable chunk | p50 < 300ms | NOW | Chunked TTS required |
| NFR-REL-001 | Barge-in cancels TTS within 200ms of UserSpeechStarted (local processing) | NOW | Race tests required |
| NFR-REL-002 | No stale LLM/TTS audio after interrupt | NOW | Sequence + cancel tests |
| NFR-REL-003 | Provider timeout does not deadlock session | NOW | Error event + recoverable |
| NFR-SCALE-001 | Compose deployment supports 5 concurrent playground sessions on a laptop-class VM | NOW | Not a production SLA |
| NFR-SCALE-002 | Runtime workers horizontally addable | NEAR | LiveKit job dispatch |
| NFR-SEC-001 | Tenant A cannot read tenant B resources | NOW | Automated isolation tests NEAR |
| NFR-SEC-002 | Secrets never committed or logged | NOW | CLAUDE.md + review |
| NFR-MAINT-001 | New LLM adapter without changing runtime loop | NOW | Contract test |
| NFR-EXT-001 | Message model supports additional ContentPart types | NOW (model), LATER (impl) | No audio-only types as identity |
| NFR-OBS-001 | Every provider call has span + duration + usage | NOW | OTel |
| NFR-TEST-001 | CI: unit + contract; realtime tests in dedicated job | NOW/NEAR | |
| NFR-PORT-001 | S3-compatible storage; local MinIO | NEAR | P1 may skip uploads |
| NFR-COST-001 | Per-session token/character estimates persisted | NEAR | P1 optional metadata |

---

## 3. Explicit non-requirements (P1)

| ID | Not required |
| --- | --- |
| NR-001 | Kubernetes, multi-region |
| NR-002 | Telephony/SIP/PSTN |
| NR-003 | Custom WebRTC stack |
| NR-004 | Tools, RAG, workflows, MCP |
| NR-005 | Multi-agent, HITL |
| NR-006 | Evaluation lab, simulation |
| NR-007 | SSO, SCIM, customer-managed keys |
| NR-008 | Mobile native apps |
| NR-009 | Agent marketplace |
| NR-010 | Implementing insurance-domain logic |

---

## 4. Requirement → P1 acceptance

Prototype 1 is **accepted** iff FR-AGT-001–008, FR-VOICE-001–006, FR-SES-001–002, FR-SEC-001–002, FR-SEC-004, FR-OBS-001, NFR-REL-001–003, NFR-MAINT-001 are demonstrable. Full checklist: [prototype-1.md](prototype-1.md).
