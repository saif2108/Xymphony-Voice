# Glossary — Canonical Vocabulary

This document is the **source of truth for terms**. Every other Phase 0 document must use these meanings. If a document needs a different meaning, change this glossary first, then update dependents.

Horizon labels used everywhere:

| Label | Meaning |
| --- | --- |
| **NOW** | Prototype 1 (implementation next; ~7–14 working days) |
| **NEAR** | Prototype 2 (~3–5 weeks after P1) |
| **LATER** | Beta → V1 |
| **VISION** | 9–24 month platform |

---

## Tenancy and product surface

### Organization

The **tenant root** and security/billing boundary. Created at signup. Owns members, roles, provider credentials, audit logs, retention policy, and Projects.

**Not** a voice session. **Not** an agent.

### Workspace

The **UX name** for the signed-in Organization home (Mission Control, sidebar, “your workspace”).

**NOW:** 1:1 with Organization. There is **no separate `workspaces` table**. Schema and APIs use `organization_id`.

**VISION:** an Organization may contain multiple Workspaces. Until that ADR exists, do not introduce a Workspace entity in code.

### Project

The **working isolation unit** inside an Organization. Agents, knowledge, tools, workflows, evaluations, and deployments live in a Project.

All control-plane resources are `(organization_id, project_id)` scoped.

### User

A human identity that can authenticate. Users belong to Organizations via Memberships.

### Membership

The join of User ↔ Organization with a role (see [security.md](security.md)).

### Environment

A named deployment target inside a Project: `development`, `staging`, `production` (**NEAR**). **NOW:** implicit `development` only (playground).

---

## Agent domain

### Agent

A **durable product identity**: “the Customer Support agent.” Mutable metadata (name, description, tags, status). Does **not** contain the executable configuration used at runtime.

Agents are not prompts. Agents are versioned products.

### AgentVersion

An **immutable configuration snapshot** of an Agent: instructions, personality, model/STT/TTS bindings, tool bindings, knowledge bindings, workflow binding, guardrails, memory policy.

Runtime loads **AgentVersion**, never “whatever is currently in the editor.”

Draft versions may be mutable **until published**. After publish, they are immutable. Edits create a new version.

### Deployment

A **binding**: AgentVersion × Environment × Channel (+ optional traffic rules).

Example: production web widget serves version 12; playground serves the draft version.

A Deployment is not a Session. Changing a Deployment does **not** mutate in-flight Sessions (see [architecture.md](architecture.md)).

### Channel

How a Session is transported: `playground`, `web_embed`, `public_api`, `telephony` (**LATER**). Transport-specific, not agent identity.

### Session

One conversation instance between a caller (human or simulator) and a Deployment (hence a specific AgentVersion).

Owns the event stream, turns, messages, and runtime state for that conversation.

### Turn

One bounded interaction cycle, typically: user input complete → agent work → agent output complete (or interrupted).

Turns have IDs. Cancellation and barge-in are turn-scoped.

### Message

A stored conversational utterance in a Session, composed of one or more **ContentParts**. Modalities: text, audio reference, image, file, video (**NOW:** text + audio reference).

Messages are the **durable transcript**. Events are the **execution log**. Do not treat them as the same object.

### ContentPart

Modality-neutral piece of a Message: `{type, payload, metadata}`. Designed so image/file/video can be added without renaming the voice stack to “audio-only messages.”

### Event

A runtime occurrence with the canonical envelope in [event-model.md](event-model.md). Events power the runtime, Live Agent Brain, traces, and (selectively) persistence.

Events are **not** LLM hidden chain-of-thought.

### Tool

A deterministic capability the runtime can invoke with a schema: HTTP, function, webhook, MCP, database, internal service.

The LLM may **select** a tool. The runtime **executes** it. Tools are the system of record for side effects.

### ToolVersion

Immutable snapshot of a Tool’s schema and execution config, referenced by AgentVersion.

### Workflow

A graph of nodes and edges that constrains/orchestrates agent behavior beyond a freeform ReAct loop. **Not** synonymous with Agent.

An Agent **may bind** a Workflow. Many Agents will have no graph in NOW/NEAR (single LLM loop).

### WorkflowVersion

Immutable snapshot of a workflow graph, referenced by AgentVersion.

### KnowledgeSource

A configured corpus (uploads, URLs, **LATER** connectors) belonging to a Project, bindable to AgentVersions.

### Document

One ingested item inside a KnowledgeSource (file, page, note).

### Chunk

A retrieval unit derived from a Document, embedded and stored in the vector store.

### Memory

**Not** a synonym for RAG. See [memory-design.md](memory-design.md). Subtypes:

| Term | Meaning |
| --- | --- |
| Conversation state | In-session working state (current turn, pending tools, cancellation) |
| Short-term memory | Rolling summary / recent-turn context |
| Long-term memory | Durable extracted facts across sessions |
| User memory | Facts about a caller identity |
| Agent memory | Optional operational notes the agent is allowed to persist |
| Knowledge | Retrieved documents (RAG); **not** memory |

### Provider

An external capability (LLM, STT, TTS, embeddings, realtime media). Runtime depends on **ports**. Implementations are **adapters**.

Never say “the OpenAI runtime.” Say “the LLM port, OpenAI adapter.”

### ProviderAdapter

A concrete implementation of a port (e.g. `OpenAILLMAdapter`).

### Agent Runtime (Xymphony Agent Runtime)

The **product core**: session/turn lifecycle, event loop, model invocation, tool execution, retrieval, workflow stepping, interruption, cancellation, observability. **Not** LiveKit. **Not** a particular LLM.

### Realtime Transport

LiveKit + WebRTC (NOW). A Session’s media path. Replaceable in principle; not the identity of the runtime.

### Playground

In-dashboard realtime test surface against a draft or published AgentVersion. Not production Deployment.

### Control plane

APIs and UI that mutate configuration, identity, and governance. Source of truth: PostgreSQL.

### Data plane

Realtime and batch execution: sessions, audio, inference, tools, retrieval. Reads **immutable version snapshots**. Does not treat the editor as live config.

### Evaluator

A scoring function (deterministic, LLM-as-judge, or human) over a trace. See [evaluation.md](evaluation.md).

### Scenario

A specified situation used in evaluation or simulation (inputs, constraints, expected outcomes).

---

## Latency terms

| Term | Meaning |
| --- | --- |
| **TTFT** | Time to first LLM token after the request is sent |
| **TTFB (TTS)** | Time to first audio byte/frame from TTS after text (or first speakable chunk) is sent |
| **Endpointing** | Deciding the user finished speaking (VAD + optional semantic endpointing) |
| **E2E response latency** | User speech end → first agent audio frame in the client |
| **Time-to-first-audio (TTFA)** | Same as E2E response latency unless specified otherwise |

---

## Status vocabulary

Agent `status`: `draft` | `active` | `archived`

AgentVersion `status`: `draft` | `published` | `deprecated`

Deployment `status`: `inactive` | `active` | `shadow` (**LATER**)

Session `status`: `initializing` | `active` | `completed` | `failed` | `terminated`

Turn `status`: `in_progress` | `committed` | `cancelled` | `failed` (barge-in sets Turn `cancelled` / Message `interrupted`; Session stays `active`)

---

## Forbidden conflations

| Do not say | Say instead |
| --- | --- |
| “the agent prompt” as the whole product | Agent + AgentVersion |
| “deploy the session” | Create a Deployment; Sessions attach to it |
| “memory” for uploaded PDFs | KnowledgeSource / RAG |
| “LiveKit agent” as our architecture | LiveKit is transport; Xymphony Agent Runtime owns the loop |
| “OpenAI function” as the tool model | Tool + ToolExecutor; OpenAI is one LLM adapter’s calling convention |
