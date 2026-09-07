# Product Specification — Xymphony Voice

**Status:** Phase 0. Nothing in this spec is implemented in the repository.  
**Architecture:** [architecture.md](architecture.md) · **Roadmap:** [roadmap.md](roadmap.md) · **UI:** [ui-system.md](ui-system.md)

---

## 1. Product statement

**Xymphony Voice is a platform for building, deploying, testing, and operating intelligent realtime AI agents.**

Users create agents, shape behavior, choose models and speech providers, attach knowledge and tools, define workflows, deploy, talk to agents in realtime (voice first, text complementary), inspect execution, evaluate, version, and improve them.

Xymphony’s long-term identity is an **operating platform for intelligent agents**, not a vertical insurance app and not a single chatbot demo.

---

## 2. Target users and personas

| Persona | Job | Primary surfaces |
| --- | --- | --- |
| **Agent builder** (core P1) | Ship a voice agent that sounds right and follows instructions | Builder, Voice studio, Playground |
| **Product engineer** | Wire tools, APIs, knowledge, workflows | Tools, Knowledge, Workflows, Inspector |
| **QA / eval owner** | Prove the agent does not regress | Evaluation, Simulation, Replay |
| **Ops / support lead** | Watch live quality, take over (LATER) | Mission Control, Analytics, HITL |
| **Platform admin** | Keys, members, retention, providers | Settings |
| **End customer** | Talk to a deployed agent | Embed / telephony (not P1) |

**P1 user:** the two internal builders (Saif + partner). External customers are not a P1 requirement.

---

## 3. Jobs to be done

1. When I have an agent idea, I want to configure it and **talk to it in minutes**, so I know the loop works.
2. When it says the wrong thing, I want to **see what happened** (transcript + structured events), so I can fix instructions or tools.
3. When I change behavior, I want **versions**, so I can ship and roll back without guessing.
4. When I connect APIs, I want **deterministic tools**, so the model cannot invent refunds.
5. When I go to production, I want **latency, cost, and error** visibility, so I can operate it.

---

## 4. Core product loop

```
CREATE → CONFIGURE → TEACH → CONNECT → TEST → EVALUATE
    → PUBLISH → DEPLOY → MONITOR → IMPROVE → VERSION → ROLLBACK
```

| Stage | P1 | P2 | Beta/V1 |
| --- | --- | --- | --- |
| Create / configure / test (voice) | Yes | Yes | Yes |
| Teach (knowledge) / connect (tools) | No | Yes | Yes |
| Evaluate / publish / deploy / monitor | Metadata only | Inspector + basic analytics | Full |
| Version / rollback | Save draft | Publish snapshot | Deployments + rollback |
| Improve (auto) / talk-to-build | No | No | LATER/VISION |

---

## 5. End-to-end product journey

For each stage: purpose, user, screen, actions, backend, data, runtime, extensions.

### 5.1 Landing page

- **Purpose:** Explain the platform; convert to signup.  
- **User:** visitor. **Screen:** marketing landing ([ui-system.md](ui-system.md)).  
- **Actions:** sign in, sign up, docs link.  
- **Backend:** none required beyond static/Next.  
- **Data:** none. **Runtime:** none.  
- **NOW:** simple page is enough. **VISION:** interactive demo.

### 5.2 Sign up

- **Purpose:** create User + Organization (Workspace UX).  
- **Actions:** register, verify (NEAR).  
- **Backend:** identity + `organizations`, `memberships` (owner).  
- **Data:** user, org. **Runtime:** none.  
- **P1 assumption:** single-org local/dev auth is acceptable if isolation model still uses `organization_id` everywhere.

### 5.3 Workspace (Mission Control)

- **Purpose:** orient: agents, recent sessions, health.  
- **Backend:** list agents, recent sessions.  
- **Data:** reads. **Runtime:** none.  
- **Extensions:** live session count, health scores (TIER 2).

### 5.4 Create agent

- **Purpose:** mint Agent + first draft AgentVersion.  
- **Actions:** name, optional describe-your-agent (**LATER**).  
- **Backend:** insert agent + version.  
- **Data:** `agents`, `agent_versions`.  
- **Runtime:** none until playground.

### 5.5 Configure personality / instructions

- **Purpose:** define how the agent talks and what it must not do.  
- **Backend:** patch draft version.  
- **Runtime:** snapshot at next session.

### 5.6 Choose LLM / STT / TTS

- **Purpose:** bind providers without hardcoding vendors in UI logic beyond a registry.  
- **Backend:** validate adapter exists + credentials for org.  
- **Data:** version provider config (IDs, not raw secrets).  
- **Runtime:** resolve adapters from snapshot.

### 5.7 Add knowledge / tools / workflow

- **NEAR/LATER.** Backend: knowledge jobs, tool registry, workflow graphs. Runtime: retrieve/execute/step.

### 5.8 Realtime test (Playground)

- **Purpose:** prove the voice loop.  
- **Actions:** connect mic, talk, interrupt, disconnect.  
- **Backend:** create Session, issue LiveKit token, persist transcript.  
- **Runtime:** full P1 pipeline.  
- **Data:** session, turns, messages, basic events.

### 5.9 Inspect session

- **NEAR:** structured event timeline. **NOW:** transcript + status timestamps.

### 5.10 Evaluate / iterate

- **LATER:** datasets, judges, sim lab. **NOW:** human listens in playground.

### 5.11 Publish / deploy / monitor / version

- **NEAR/LATER.** See [deployment.md](deployment.md), [observability.md](observability.md).

---

## 6. Agent conceptual model (product)

An Agent is **not** `{name, prompt}`.

**Agent (identity):** name, description, status, project, created_by, timestamps, tags.

**AgentVersion (behavior snapshot):**

- identity linkage (`agent_id`, `semver` or monotonic `version_n`)
- instructions, personality, goals[], constraints[]
- locale/language
- model / STT / TTS bindings (provider_id + model/voice ids + params)
- knowledge bindings[], tool bindings[], workflow binding?
- memory policy, safety/guardrails, escalation policy
- metadata, status (`draft`/`published`), created_by, timestamps

**Deployment:** environment + channel + `agent_version_id` + status.

**Session:** execution instance of a Deployment (or playground pointing at a version).

Product rule: **editing the builder never mutates an active Session.**

---

## 7. Standout features (architecture must allow; do not implement all)

**Tier 1** (platform must not paint us into a corner): voice-first builder, describe-your-agent, realtime playground, visual workflows, live agent brain, replay, structured traces, RAG, tools/MCP, versioning, eval/sim, latency+cost analytics.

**Tier 2:** talk-to-build, auto improvement, model playground/routing, health score, conversation intelligence, human takeover, shadow deploys.

**Tier 3:** autonomous optimization, long-term memory, multi-agent, multimodal, self-host, enterprise governance, telephony, marketplace, A2A, auto workflow generation.

Feature designs:

- Describe-your-agent / talk-to-build / brain / why: [ui-system.md](ui-system.md) and §8–10 below  
- Eval/sim: [evaluation.md](evaluation.md)  
- Multi-agent: [multi-agent-design.md](multi-agent-design.md)

---

## 8. Describe-your-agent (LATER)

User text: *“Build a customer support agent for e-commerce that answers order questions, looks up orders, refunds under $100, escalates angry customers.”*

Pipeline (provider-agnostic):

1. Builder LLM call via **LLM port** with a **strict JSON schema** (instructions, goals, constraints, suggested tools, knowledge needs, workflow sketch, eval scenarios, model/voice recommendations).
2. Validate schema; map to draft AgentVersion + draft Tool stubs (no credentials).
3. Show diff/preview; **user confirms**.
4. Never write production Deployment.

The builder agent is a **separate AgentVersion** (meta-agent) with no prod tool side effects.

---

## 9. Talk-to-build (VISION/TIER 2)

Same as §8 but input is voice → STT → Builder Agent. Confirmation is mandatory. Production mutations require the same control-plane authorization as the dashboard (the voice channel is not a privilege escalation path).

---

## 10. Live Agent Brain and “why did it do that?”

UI shows **structured events**: user said → transcript → retrieve → tool selected → tool result → response → TTS.

**Forbidden:** hidden chain-of-thought, raw provider reasoning dumps.

“Why escalate?” uses: matched guardrail/workflow node, tool outputs, configured policy id, classifier label if we explicitly emit one as an event. See [event-model.md](event-model.md).

---

## 11. Cost optimization (LATER)

Offline job reads session metrics (tokens, STT duration, TTS characters, tool latency) and proposes: smaller model, routing rules, shorter context, cache, provider switch. Applies only via new AgentVersion + user/apply policy — never silent prod mutation.

---

## 12. Feature priorities

| Priority | Items |
| --- | --- |
| P0 Prototype 1 | Agent CRUD draft, provider select, playground voice, barge-in, transcript, save |
| P1 Prototype 2 | RAG, tools/MCP, inspector, more adapters, analytics basics |
| P2 Beta | Version publish, workflows, eval, HITL, memory v1, stronger OTel |
| P3 V1 | Deploy channels, RBAC complete, SDK, routing, simulation |
| P4 Vision | Telephony, multi-agent, marketplace, on-prem |

---

## 13. Non-goals

- Recreating the insurance POC as the product  
- Building our own ASR/TTS/LLM  
- Building our own WebRTC SFU  
- Kubernetes-first ops  
- Treating the LLM as the ledger for money-moving operations  
- Shipping all Tier 1 UI in P1  

---

## 14. Success metrics (product)

P1: a builder creates an agent and completes a barged-in multi-turn voice conversation in one sitting.

V1: an external team can deploy a tool-using, knowledge-grounded voice agent with versioning, traces, and basic eval — without forking the runtime.
