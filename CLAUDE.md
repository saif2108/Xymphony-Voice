# Xymphony Voice --- Permanent AI Engineering Context

## Project Identity

**Project:** Xymphony Voice\
**Repository:** `https://github.com/saif2108/Xymphony-Voice.git`

Xymphony Voice is a platform for **building, deploying, and operating
intelligent real-time voice agents**. It is a platform, not a single
voice chatbot or vertical application.

Product direction:

> **Xymphony Voice --- Build, deploy, and operate intelligent real-time
> voice agents.**

Broader direction:

> **Xymphony becomes the operating platform for intelligent AI agents.**

Voice is first-class, while text remains a first-class modality.

## Core Principles

1.  Build a platform, not a single vertical application.
2.  Separate control plane from realtime data plane.
3.  Keep media transport separate from agent reasoning/orchestration.
4.  LLMs handle language/reasoning; deterministic tools enforce business
    rules and side effects.
5.  STT, LLM, and TTS integrations use provider-neutral ports/adapters.
6.  Conversation state, persistence, cancellation, interruption,
    observability, and evaluation are first-class.
7.  Build small initially while preserving scalable boundaries.
8.  Do not rebuild proprietary models or WebRTC infrastructure
    unnecessarily.
9.  Prefer simple infrastructure until scale requires more.
10. Git/source code is the implementation source of truth.

## Current Checkpoint

Completed:

-   Phase 1
-   Phase 2
-   Phase 3 Step 1
-   Phase 3 Step 2
-   Phase 3 Step 3

Current Git checkpoint:

`ec97948` --- `Phase 3 Step 3: add conversation summarization`

Phase 3 Step 3 includes provider-neutral context assembly, deterministic
context budgeting, lazy rolling conversation summarization, persistent
summaries, summary coverage tracking via `through_sequence`,
summary-aware budgeting, cancellation safety, soft summary failure, and
preservation of the original conversation ledger.

PostgreSQL integration has not been fully exercised locally because the
current development environment does not have the required
PostgreSQL/Docker setup. Do not introduce Docker, WSL, Kubernetes, or
similar infrastructure merely to work around this unless it becomes
necessary.

## High-Level Architecture

``` text
OUR PLATFORM
├── Dashboard / UI
├── Control Plane
│   ├── Organizations / Projects
│   ├── Agents / Agent Versions
│   ├── Deployments
│   ├── Users / Authentication
│   ├── Knowledge
│   ├── Workflows
│   ├── API / SDK
│   └── Analytics
├── Data Plane / Agent Runtime
│   ├── Media Transport
│   ├── VAD / Turn Detection
│   ├── STT
│   ├── LLM
│   ├── TTS
│   ├── Streaming
│   ├── Barge-in / Cancellation
│   ├── Tools
│   ├── RAG
│   ├── Memory
│   ├── Workflows / Subagents
│   └── Event / Frame Bus
├── Data Layer
│   ├── PostgreSQL
│   ├── Redis
│   ├── pgvector
│   └── S3 / MinIO
└── Observability / Evaluation
    ├── OpenTelemetry
    ├── Logs / Metrics / Traces
    ├── Evaluation
    └── Usage / Cost
```

## Control Plane vs Data Plane

### Control Plane

Owns configuration and management:

-   organizations and projects
-   agents and versions
-   deployments
-   knowledge
-   workflows
-   tools
-   authentication
-   API keys
-   analytics configuration

It must not own the realtime audio loop.

### Data Plane

Owns active sessions:

-   realtime media
-   STT
-   LLM streaming
-   TTS streaming
-   interruptions
-   cancellation
-   tools
-   workflows
-   conversation state
-   memory
-   realtime events

Realtime sessions must not depend on dashboard/API request latency.

## Runtime Architecture

``` text
User Audio
  ↓
Media Transport
  ↓
Runtime Media Bridge
  ↓
Agent Runtime
  ↓
STT
  ↓
Transcript
  ↓
Conversation / Context Assembly
  ↓
LLM
  ↓
Tools / Workflows when required
  ↓
LLM response
  ↓
TTS
  ↓
Media Transport
  ↓
User
```

Voice and text should converge into the same reasoning/runtime path.

## Media Transport

LiveKit is a **media transport**, not the Xymphony agent runtime.

Use a vendor-neutral `MediaTransport` abstraction.

Conceptually:

``` text
MediaTransport
├── LiveKitMediaTransport
├── FakeMediaTransport
└── Future transports
```

LiveKit handles realtime media/WebRTC transport. Xymphony owns agent
execution, provider orchestration, conversation state, tools, workflows,
memory, observability, and platform behavior.

Do not make the core runtime dependent on a managed agent framework.

## Provider Abstraction

STT, LLM, and TTS are provider ports/adapters.

``` text
Agent Runtime
├── LLMProvider
│   ├── OpenAI
│   ├── Anthropic
│   ├── Gemini
│   ├── Ollama
│   └── future providers
├── STTProvider
│   ├── AssemblyAI
│   ├── Whisper
│   └── future providers
└── TTSProvider
    ├── ElevenLabs
    ├── Cartesia
    ├── Piper
    └── future providers
```

Provider SDK behavior belongs in adapters. Core runtime logic must
remain provider-neutral. Prefer dependency injection and never construct
providers implicitly inside the core runtime.

## Context and Memory

Current context flow:

``` text
Conversation Repository
  ↓
Committed messages
  ↓
LLMContextAssembler
  ↓
Conversation summary when required
  ↓
Context budget
  ↓
LLMRequest
```

The context budget prioritizes:

1.  system context
2.  current user input
3.  conversation summary
4.  newest complete history

If the system/current user content cannot fit, fail explicitly. Do not
silently corrupt the request.

The current token estimator is intentionally approximate and isolated
behind an abstraction.

### Conversation Summaries

A summary is derived context, not a replacement for the conversation
ledger.

``` text
Session
├── ConversationMessage[]
└── ConversationSummary
    ├── through_sequence
    ├── summary_text
    └── source_message_count
```

Rules:

1.  Never delete original messages because of summarization.
2.  One rolling summary per session for now.
3.  `through_sequence` is the inclusive end of summarized history.
4.  Summarize lazily only when context budgeting would otherwise drop
    history.
5.  Initially use the same injected LLM provider/config.
6.  Inject the summary as dedicated system context, not fake
    conversation turns.
7.  Include summary tokens in the same context budget.
8.  Summarization must be cancellation-safe.
9.  Summary failure is a soft failure; continue with budgeted recent
    history.
10. Advance coverage only after successful persistence.
11. Avoid re-summarizing already covered messages.

Future options include cheaper summary models, background summarization,
hierarchical summaries, configurable retention, and semantic memory.

## Sessions and Persistence

Relationship:

``` text
Organization
  ↓
Project
  ↓
Agent
  ↓
AgentVersion
  ↓
Session
  ↓
ConversationMessage[]
```

A session is the conversation boundary and is pinned to an immutable
agent-version/configuration snapshot.

Published agent versions are immutable. Changes should produce a new
version rather than mutating a published version.

Cancelled turns must not create misleading committed assistant messages.

PostgreSQL is the system of record. Redis is not the authoritative
conversation ledger.

## Event Model

Important provider-neutral events include:

``` text
AudioFrame
TextFrame
UserSpeechStarted
UserSpeechEnded
TranscriptFrame
LLMToken
LLMResponse
ToolCall
ToolResult
TTSChunk
AgentInterrupted
AgentTransferred
WorkflowTransition
Error
```

Common metadata should include event ID, event type, timestamp, session
ID, turn ID, sequence, and payload where applicable.

### Cancellation

Cancellation is turn-scoped.

A barge-in cancels the active turn without destroying the session.

Stale results from cancelled turns must not reach the user or mutate
newer turns.

## Current Realtime Flow

``` text
Browser microphone
  ↓
LiveKit
  ↓
MediaTransport
  ↓
RuntimeMediaBridge
  ↓
AgentRuntime
  ↓
STT
  ↓
TranscriptFrame
  ↓
LLM context
  ↓
LLM streaming
  ↓
TTS streaming
  ↓
TTS audio resolution
  ↓
TransportAudioOutputFrame
  ↓
LiveKit AudioSource
  ↓
Browser speaker
```

Advanced VAD/endpointing and production repair behavior remain future
work.

## Voice Reliability / Repair

Future architecture should include a reliability/repair layer:

``` text
Audio
 ↓
STT
 ↓
Voice Reliability / Repair
 ↓
Agent Runtime
 ↓
LLM
 ↓
Tools
 ↓
TTS
```

Possible decisions:

-   Proceed
-   Clarify
-   Confirm
-   Retry
-   Repair
-   Escalate

It should address STT ambiguity, missing information, contradictory
answers, unclear intent, failed tools, and recoverable provider errors.

## Tools and Business Logic

The LLM reasons and communicates; deterministic tools execute and
enforce business rules.

``` text
LLM
 ↓
Tool call
 ↓
Validation / authorization / business rules
 ↓
Side effect
 ↓
Tool result
```

Future tool schemas should support description, when-to-use,
when-not-to-use, confirmation requirements, risk level, input schema,
and output schema.

Do not put deterministic business rules solely inside prompts.

## RAG / Knowledge

Future flow:

``` text
Documents
 ↓
Ingestion
 ↓
Chunking
 ↓
Embeddings
 ↓
Vector store
 ↓
Retrieval
 ↓
Context
 ↓
LLM
```

Initial data direction:

-   PostgreSQL as system of record
-   pgvector for vectors
-   S3/MinIO for objects/documents
-   Redis for cache/session/pubsub use cases

Do not introduce a dedicated vector database prematurely.

## Workflows

Workflows will eventually support branching, tools, retries, handoffs,
human-in-the-loop, state transitions, and subagents.

LangGraph may be used inside a future workflow executor where durable
graph execution is useful.

**LangGraph must not become the realtime voice loop.**

The realtime runtime remains responsible for streaming, interruption,
cancellation, turn lifecycle, and media behavior.

## Repository Structure

``` text
xymphony-voice/
├── apps/
│   ├── dashboard/
│   ├── api/
│   └── playground/
├── packages/
│   ├── contracts/
│   ├── agent-runtime/
│   ├── realtime/
│   ├── providers/
│   ├── workflows/
│   ├── tools/
│   ├── rag/
│   ├── memory/
│   └── evaluation/
├── infrastructure/
│   ├── docker/
│   └── deployment/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── realtime/
│   ├── evaluation/
│   └── e2e/
├── docs/
├── docker-compose.yml
├── README.md
├── CLAUDE.md
└── pyproject.toml
```

Do not create empty abstractions solely because a future directory
exists.

## Recommended Stack

### Backend

-   Python
-   FastAPI
-   Pydantic
-   SQLAlchemy
-   Alembic
-   PostgreSQL + pgvector
-   Redis
-   ARQ for asynchronous jobs when justified
-   Pytest
-   Ruff
-   mypy

### Frontend

-   Next.js
-   React
-   TypeScript
-   Tailwind CSS
-   shadcn/ui
-   React Flow where visual workflow editing is required

### Realtime

-   LiveKit for media transport
-   Xymphony Agent Runtime for orchestration

### Observability

-   OpenTelemetry
-   structured logs
-   metrics
-   traces
-   usage/cost tracking

### Infrastructure

-   Docker Compose for local multi-service development
-   LiveKit Cloud for realtime development
-   Kubernetes only when production scale justifies it

## Security

Production architecture must include:

-   authentication
-   authorization/RBAC
-   organization/project isolation
-   API keys
-   secure secret storage
-   rate limiting
-   audit logs
-   input validation
-   tool authorization
-   tool sandboxing where required
-   no secrets in source control
-   no secrets in logs
-   tenant isolation at persistence boundaries

Security belongs in APIs/services/persistence, not only the UI.

## Testing Strategy

### Unit

Test contracts, runtime lifecycle, cancellation, event admission,
providers, context assembly, budgeting, summarization, repositories, and
business logic.

### Integration

Test PostgreSQL persistence, migrations, API/database behavior, and
provider integrations where practical.

### Realtime

Test audio flow, turn boundaries, interruptions, cancellation, stale
output, repeated turns, provider failures, and transport failures.

### E2E

The eventual end-to-end test should cover:

``` text
Dashboard
 → create/configure agent
 → publish
 → launch session
 → speak
 → STT
 → LLM
 → TTS
 → hear response
 → interrupt
 → continue
```

Use targeted tests during implementation and broader regression testing
at major milestones. High-risk runtime/realtime changes require stronger
testing.

## Definition of Done

Every meaningful step should satisfy:

``` text
✓ Implemented
✓ Typed
✓ Tested
✓ Integrated
✓ Error handled
✓ Logged where appropriate
✓ Documented
✓ UI works where applicable
✓ No regression
✓ Git checkpoint
```

Realtime additions also require:

``` text
✓ Interruption tested
✓ Cancellation tested
✓ Multiple turns tested
✓ Network degradation considered
✓ Provider failure tested
```

## Coding Rules for AI Assistants

Before coding:

1.  Inspect the existing architecture.
2.  Identify the actual integration point.
3.  Reuse existing abstractions.
4.  Avoid duplicate concepts.
5.  Check existing tests.

While coding:

1.  Make the smallest architecture-consistent change.
2.  Do not rewrite unrelated code.
3.  Preserve public contracts unless explicitly required otherwise.
4.  Use dependency injection.
5.  Keep provider-specific code in adapters.
6.  Keep API routes thin.
7.  Keep UI business logic out of components.
8.  Keep deterministic business rules in tools/services.
9.  Avoid unnecessary infrastructure.
10. Never hardcode or expose secrets.
11. Do not silently change semantics to make tests pass.

After coding, report:

-   files changed/added
-   architectural impact
-   tests run/results
-   lint/type-check results
-   known limitations
-   unavailable integration tests
-   migration requirements

AI assistants should not commit or push unless explicitly instructed.

## Git Workflow

GitHub is the implementation source of truth.

### Person 1

Primarily owns backend, runtime, realtime, contracts, infrastructure,
persistence, and provider architecture.

Default branch:

``` text
main
```

### Person 2

Primarily owns dashboard/frontend.

Branch:

``` text
person2/dashboard
```

Person 2 should not directly push to `main`.

### Synchronization

Before integrating Person 2 work:

``` powershell
git fetch origin
git log --oneline main..origin/person2/dashboard
git status
```

Person 2 can synchronize with main using:

``` powershell
git fetch origin
git merge origin/main
```

Person 1 can synchronize main using:

``` powershell
git pull origin main
```

If conflicts occur, stop and coordinate rather than forcing a
resolution.

### Checkpoints

For meaningful milestones:

``` powershell
git add <specific files>
git status
git commit -m "Phase X Step Y: <description>"
git push origin main
```

Avoid blindly using `git add .` when unrelated changes may exist. Always
inspect staged changes before committing.

## AI Development Workflow

For major steps:

``` text
1. Architecture inspection
2. Define implementation scope
3. One strong implementation prompt where practical
4. AI implementation
5. Review implementation report
6. Targeted tests
7. Lint/type checks
8. Review diff
9. Git checkpoint
10. Update status/context
```

Avoid repeated low-value AI audits. Extra review is appropriate for
persistence migrations, cancellation/realtime semantics, security,
concurrency, provider abstractions, and state machines.

## What Not To Build

Do not:

-   rebuild Whisper from scratch
-   train an LLM
-   build proprietary TTS/STT models
-   implement WebRTC from scratch
-   recreate a media server
-   hardcode one provider into the runtime
-   make LiveKit the application architecture
-   make LangGraph the realtime audio loop
-   introduce Kafka prematurely
-   introduce Kubernetes prematurely
-   introduce dozens of providers prematurely
-   create empty abstraction layers
-   copy the insurance POC's business logic into the platform core

## Insurance POC

The earlier automobile insurance voice agent proved the concept.

Its platform mapping is:

``` text
Old POC
├── Voice I/O
├── Insurance state
├── History
├── RAG
├── Tools
└── LLM loop

Xymphony Voice
├── Generic voice/runtime
├── Generic session state
├── Generic conversation history
├── Generic RAG
├── Generic tools
├── Provider abstraction
└── Generic agent runtime
```

The insurance application should become a vertical application running
on Xymphony Voice, not define the platform core.

## Roadmap to V1

### Phase 1 --- Foundation

Completed.

Contracts, control-plane foundations, agent/version model, media
transport abstraction, and initial persistence.

### Phase 2 --- Realtime Agent Runtime

Completed.

Runtime lifecycle, LLM/STT/TTS ports, streaming, cancellation, media
bridge, LiveKit audio path, sessions, conversation persistence, and
worker bootstrap.

### Phase 3 --- Context / Memory Foundation

Current phase; completed through Step 3.

Includes context assembly, context budgeting, and conversation
summarization.

### Phase 4 --- Agent Builder

Target:

-   structured/visual agent configuration
-   prompts/personality
-   provider selection
-   voice configuration
-   tools
-   knowledge
-   deployment configuration
-   playground UX

### Phase 5 --- Knowledge / Tools / Workflows

Target:

-   RAG
-   tool registry
-   APIs/webhooks
-   MCP
-   workflow execution
-   deterministic branching
-   handoffs

### Phase 6 --- Advanced Agent Platform

Target:

-   memory
-   multi-agent
-   advanced workflows
-   human-in-the-loop
-   advanced realtime behavior
-   broader provider flexibility

### Phase 7 --- Strong Platform Prototype

Target:

-   complete platform experience
-   robust builder
-   voice playground
-   knowledge
-   tools
-   workflows
-   inspection
-   analytics
-   multiple providers

This is a major prototype/beta milestone, **not final V1**.

### Phase 8 --- Production Hardening

Target:

-   authentication
-   RBAC
-   API keys
-   security
-   tenant isolation
-   rate limits
-   secrets management
-   provider failover
-   reliability/repair
-   recovery

### Phase 9 --- Production Operations

Target:

-   deployment
-   horizontal scaling
-   distributed workers where justified
-   OpenTelemetry
-   metrics
-   usage/cost
-   load testing
-   evaluation
-   CI/CD
-   backup/recovery

### Phase 10 --- V1 Release

Target:

-   full regression
-   security review
-   UX polish
-   stable API/SDK
-   production deployment
-   finalized lifecycle/versioning
-   performance validation
-   reliability validation
-   documentation

Approximate planning:

-   first usable prototype: \~1--2 weeks
-   strong platform prototype: \~6--12 weeks
-   serious competitor-level platform: \~3--6 months
-   launchable V1: \~4--6 months
-   broader mature Xymphony vision: \~9--15+ months

These are estimates, not deadlines.

## Source-of-Truth Hierarchy

When information conflicts:

1.  actual source code
2.  tests
3.  database migrations/schema
4.  current Git history
5.  `CLAUDE.md`
6.  current project status documents
7.  older conversational descriptions

`CLAUDE.md` provides permanent engineering rules/context. It does not
prove that a feature exists. Inspect source/tests before making
implementation claims.

## Working With Regular Claude / Claude Projects

This file is permanent project context.

For an individual task, provide:

1.  this `CLAUDE.md`
2.  the task
3.  relevant source files/folders
4.  relevant tests where necessary

Do not assume the entire repository is available in a normal Claude web
conversation.

Do not upload the entire repository as permanent Project Knowledge
merely for a single task.

The repository/GitHub source remains the implementation source of truth.

## Final Engineering Principle

> **Xymphony Voice owns the agent runtime and platform abstractions;
> external providers and infrastructure supply specialized
> capabilities.**

The platform should continuously move toward:

``` text
Build
 ↓
Configure
 ↓
Deploy
 ↓
Talk
 ↓
Reason
 ↓
Act
 ↓
Observe
 ↓
Evaluate
 ↓
Improve
```

while maintaining clean separation between:

``` text
Media
Runtime
Providers
State
Tools
Knowledge
Workflows
Control Plane
Observability
```
