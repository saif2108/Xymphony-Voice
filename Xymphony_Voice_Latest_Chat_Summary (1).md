# Xymphony Voice — Latest Chat Summary

**Date:** September 9, 2026  
**Project:** Xymphony Voice  
**Role:** Person 2 — Dashboard / Frontend / UX

---

## 1. Project Context

Repository:

`https://github.com/saif2108/Xymphony-Voice.git`

Xymphony Voice is being developed as a platform to:

> Build, deploy, and operate intelligent real-time voice agents.

Long-term product areas include:

- Agent creation and configuration
- Voice and text interactions
- Realtime sessions
- Multiple LLM/STT/TTS providers
- Tools/function calling
- APIs/webhooks/MCP
- RAG/knowledge
- Memory
- Workflows
- Multi-agent behavior and handoff
- Evaluation
- Observability and analytics
- Deployment and telephony
- Versioning
- Multi-tenancy
- Developer/API access

### Architecture

The major layers are:

1. **Dashboard / Control Plane**
   - Agent configuration
   - Projects / organizations / users
   - Knowledge
   - Workflows
   - API / SDK
   - Analytics

2. **Data Plane / Agent Runtime**
   - Media transport
   - VAD / turn detection
   - STT
   - LLM
   - TTS
   - Streaming
   - Barge-in / cancellation
   - Tools
   - RAG
   - Memory / state
   - Workflows / subagents
   - Event/frame bus

3. **Data Layer**
   - PostgreSQL
   - pgvector
   - Redis
   - S3 / MinIO

4. **Observability / Evaluation**

Important architectural principle:

**LiveKit is media transport infrastructure, not the core agent runtime abstraction.**

The Xymphony Agent Runtime owns agent execution.

---

## 2. Control Plane vs Data Plane

### Control Plane

Responsible for:

- Agent configuration
- Projects / organizations
- Agent versions
- API
- Dashboard
- Knowledge
- Workflow configuration
- Analytics

### Data Plane

Responsible for:

- Realtime sessions
- Media
- STT
- LLM
- TTS
- Tools
- Runtime state
- Realtime execution

Realtime execution should remain independent of dashboard request latency.

---

## 3. Current Phase / Status

Phase 1 is complete.

Phase 2 is complete.

Phase 3 has started.

### Phase 2

Phase 2 delivered:

- AgentRuntime
- RuntimeContext
- Turn lifecycle
- Input dispatch
- Streaming
- Cancellation
- Event admission
- Stale-output protection
- Provider-neutral LLM abstraction
- OpenAI adapter
- Fake LLM
- STT contract
- AssemblyAI adapter
- Fake STT
- TTS contract
- ElevenLabs adapter
- Fake TTS
- RuntimeMediaBridge
- LiveKit voice path
- Session persistence
- Conversation persistence
- Version/config hash
- Runtime worker
- Barge-in
- Lifecycle/error handling
- Structured logging

Final Phase 2 checkpoint:

`4d287f2`

### Phase 3 Step 2

Person 1 implemented:

**Context Window Budgeting**

Commit:

`50980bb`

Main additions include:

- `context_budget.py`
- `llm_context.py`
- `token_estimate.py`
- Tests
- `LLMRuntimeConfig.max_input_tokens`

Current policy:

- Reserve system prompt + current user message
- Keep newest complete history
- Approximate token estimation using ~4 chars/token
- Do not mutate or reorder committed messages
- No summarization yet
- No per-message truncation yet
- No RAG/memory integration yet

Important:

The current AgentVersion API does **not** expose `max_input_tokens`, so the frontend must not invent that field.

---

## 4. Team Responsibilities

### Person 1

Owns:

- Backend
- Agent Runtime
- Realtime
- Contracts
- Provider adapters
- API
- Persistence
- Infrastructure
- Runtime worker
- Architecture
- Integration

### Person 2 — Me

Owns:

- Dashboard
- Frontend
- UX
- Agent builder UI
- Playground UI
- Frontend/API integration
- Visual workflow UI later

Avoid modifying:

- Runtime internals
- Realtime core
- Provider internals
- Persistence internals
- Shared contracts unless coordinated

---

## 5. Git Workflow

Person 2 works on:

`person2/dashboard`

Person 1 generally works on:

`main`

Person 2 should:

- Push frontend work to `person2/dashboard`
- Not push directly to `main`
- Sync from `origin/main`
- Person 1 merges dashboard changes into main

Latest branch situation:

- `person2/dashboard` already contains latest `origin/main`
- No new commits were found when running:

```powershell
git fetch origin
git log --oneline HEAD..origin/main
```

The command returned no output.

The branch was ahead of `origin/person2/dashboard` by several commits during setup, and the dashboard checkpoint was subsequently committed and pushed.

---

# 6. Dashboard Work Completed

Initially the repository did not contain:

`apps/dashboard`

We created the Next.js dashboard there.

Tech stack:

- Next.js
- React
- TypeScript
- Tailwind
- lucide-react

The user specifically requested:

- White themed
- No gradients
- No emojis
- Minimal
- Professional
- Should not look "vibe coded"

This became the design direction.

---

## 7. Dashboard Design System

The intended design language is:

**Linear × Vercel × modern AI IDE × mission control**

But implemented as a restrained white UI.

Principles:

- White background
- Neutral/zinc surfaces
- Subtle borders
- High contrast
- Dense but readable
- Minimal decoration
- No unnecessary gradients
- No excessive rounded cards
- No decorative animations
- Functional rather than flashy

Original design document:

`docs/ui-system.md`

Information architecture includes:

```text
/
├── sign-in
├── sign-up
└── [org]
    ├── agents
    │   ├── new
    │   └── [id]
    │       ├── overview
    │       ├── voice
    │       ├── knowledge
    │       ├── tools
    │       ├── workflow
    │       ├── playground
    │       └── versions
    ├── sessions/[id]
    ├── evaluations
    ├── simulations
    ├── analytics
    └── settings
```

The playground is a dashboard route, not a separate product.

---

# 8. Current Dashboard Files

Important files created/updated:

```text
apps/dashboard/
├── app/
│   ├── globals.css
│   ├── layout.tsx
│   ├── page.tsx
│   ├── components/
│   │   └── dashboard-shell.tsx
│   └── agents/
│       ├── page.tsx
│       └── new/
│           └── page.tsx
```

---

## 9. Global CSS

Current `apps/dashboard/app/globals.css`:

```css
@import "tailwindcss";

:root {
  --background: #ffffff;
  --foreground: #171717;
}

@theme inline {
  --color-background: var(--background);
  --color-foreground: var(--foreground);
}

* {
  box-sizing: border-box;
}

html,
body {
  min-height: 100%;
}

body {
  margin: 0;
  background: var(--background);
  color: var(--foreground);
  font-family: Arial, Helvetica, sans-serif;
}

button,
a {
  -webkit-tap-highlight-color: transparent;
}
```

---

## 10. Dashboard Shell

Created:

`apps/dashboard/app/components/dashboard-shell.tsx`

This is a client component.

It provides the shared:

- Sidebar
- Header
- Navigation
- Create Agent button
- Main dashboard layout

Navigation includes:

- Overview
- Agents
- Sessions
- Analytics
- Developer API
- Members
- Settings

It uses `usePathname()` to determine active navigation.

---

# 11. Overview Page

`apps/dashboard/app/page.tsx`

Uses the shared `DashboardShell`.

Currently provides:

- Dashboard overview
- Basic stats placeholders
- Get Started area

The `/` route works.

---

# 12. Agents Page

`apps/dashboard/app/agents/page.tsx`

The Agents page:

- Uses the shared dashboard shell
- Fetches agents from the backend
- Supports search/filter
- Handles loading state
- Handles errors
- Handles empty state
- Links each agent to:

```text
/agents/{agent.id}/overview
```

Backend request:

```text
GET
/v1/projects/00000000-0000-4000-8000-000000000002/agents
```

The API currently returns:

```json
{
  "items": [],
  "next_cursor": null
}
```

So the empty state is currently expected.

The `/agents` route works.

---

# 13. Create Agent Screen

Created:

```text
apps/dashboard/app/agents/new/page.tsx
```

Current Create Agent screen collects:

- Name
- Description
- Tags

It sends:

```json
{
  "name": "...",
  "description": "...",
  "status": "draft",
  "tags": ["..."]
}
```

POST endpoint:

```text
POST
/v1/projects/00000000-0000-4000-8000-000000000002/agents
```

After creation it redirects to:

```text
/agents/{agent.id}/overview
```

Important architectural decision:

### Create Agent initially only creates the Agent.

The first AgentVersion will be configured from the Agent Overview / Builder.

We should **not** invent unsupported fields.

---

# 14. Backend Agent API

Actual backend schemas were inspected.

File:

`apps/api/src/xymphony_api/schemas.py`

Current AgentCreateRequest:

```py
class AgentCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=4000)
    status: AgentStatus = AgentStatus.DRAFT
    tags: list[str] = Field(default_factory=list)
```

AgentUpdateRequest supports:

```text
name
description
status
tags
```

AgentVersionCreateRequest supports:

```text
instructions
personality
locale
llm
stt
tts
```

Specifically:

```py
class AgentVersionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    instructions: str
    personality: str
    locale: str
    llm: LLMBinding
    stt: STTBinding
    tts: TTSBinding
```

---

# 15. Agent API Routes

File:

`apps/api/src/xymphony_api/routes/agents.py`

Relevant endpoints:

```text
POST   /v1/projects/{project_id}/agents
GET    /v1/projects/{project_id}/agents

GET    /v1/projects/{project_id}/agents/{agent_id}
PATCH  /v1/projects/{project_id}/agents/{agent_id}
DELETE /v1/projects/{project_id}/agents/{agent_id}

POST   /v1/projects/{project_id}/agents/{agent_id}/versions

GET    /v1/projects/{project_id}/agents/{agent_id}/versions
GET    /v1/projects/{project_id}/agents/{agent_id}/versions/{version_id}
PATCH  /v1/projects/{project_id}/agents/{agent_id}/versions/{version_id}

POST   /v1/projects/{project_id}/agents/{agent_id}/versions/{version_id}/publish
```

Agent creation service:

- Validates project
- Generates UUID
- Stores name
- Stores description
- Stores status
- Stores tags

Version creation:

- Validates agent
- Creates AgentVersion snapshot
- Stores instructions
- Stores personality
- Stores locale
- Stores LLM/STT/TTS bindings
- Computes configuration hash

Published versions become immutable.

---

# 16. Provider Contracts

We inspected:

`packages/contracts/src/xymphony_contracts/providers.py`

Current bindings:

```py
class LLMBinding(FrozenModel):
    provider_key: str
    model: str
    params: dict[str, JsonValue]
```

```py
class STTBinding(FrozenModel):
    provider_key: str
    model: str
    params: dict[str, JsonValue]
```

```py
class TTSBinding(FrozenModel):
    provider_key: str
    voice_ref: str
    params: dict[str, JsonValue]
```

All are frozen and reject unknown/secret provider fields.

Secret-like fields such as:

- api_key
- secret
- password
- token
- authorization
- private_key

must not be stored in provider params.

---

# 17. Currently Supported Real Providers

We inspected:

`packages/providers/src/xymphony_providers/registry.py`

Current supported real providers:

### LLM

```text
openai
```

Alias:

```text
openai_compatible → openai
```

### STT

```text
assemblyai
```

### TTS

```text
elevenlabs
```

Fake providers also exist for tests.

Do not create a UI pretending Anthropic/Gemini/etc. are supported until their adapters actually exist.

---

# 18. Provider Defaults

`.env.example` contains:

```text
OPENAI_MODEL=gpt-4o-mini
ASSEMBLYAI_MODEL=universal-streaming
ELEVENLABS_VOICE_ID=voice_default
```

Credentials are environment variables:

```text
OPENAI_API_KEY
ASSEMBLYAI_API_KEY
ELEVENLABS_API_KEY
```

These credentials should never be exposed in the dashboard provider configuration.

---

# 19. Provider Details

### OpenAI

Provider key:

```text
openai
```

The model comes from the binding.

Currently supported request parameter:

```text
temperature
```

### AssemblyAI

Provider key:

```text
assemblyai
```

Default/current model:

```text
universal-streaming
```

The adapter maps that to the AssemblyAI streaming model.

### ElevenLabs

Provider key:

```text
elevenlabs
```

Uses:

```text
voice_ref
```

Optional parameters include:

```text
model_id
output_format
```

Default output format:

```text
pcm_16000
```

---

# 20. Planned Agent Builder

The next major dashboard feature is the Agent Builder.

Current proposed structure:

```text
Agent Overview

General
  Name
  Description
  Tags

Behavior
  Instructions
  Personality
  Locale

AI Configuration
  LLM
    Provider: OpenAI
    Model: gpt-4o-mini

  Speech-to-Text
    Provider: AssemblyAI
    Model: universal-streaming

  Text-to-Speech
    Provider: ElevenLabs
    Voice: voice_default

Save Draft
```

Important:

Do not expose raw provider `params` JSON in the main UI yet.

Advanced provider parameters can be added later.

---

# 21. Voice-Based Agent Creation Question

The user asked whether a user can currently create an agent by speaking rather than manually filling out fields.

Answer:

**Not currently. That functionality has to be built.**

The backend already has:

- STT
- LLM
- TTS
- Realtime runtime
- Agent creation APIs
- AgentVersion APIs

But it does NOT currently have an orchestration layer that performs:

```text
User speech
→ STT
→ understand requirements
→ structured agent configuration
→ create Agent / AgentVersion
```

A future flow could be:

```text
User speaks
      ↓
Browser microphone
      ↓
STT
      ↓
Agent Creation LLM
      ↓
Structured agent config
      ↓
Draft configuration
      ↓
User reviews/edits
      ↓
Create Agent API
      ↓
Agent + Version
```

This should be treated as a future Phase 3 capability.

It is **not explicitly committed in the current roadmap**.

The roadmap explicitly includes:

- Agent creation/configuration
- Voice-enabled playground

But conversational voice-to-create-agent is not currently listed as a committed feature.

It can be added later as a UX layer on top of the Agent Builder.

---

# 22. Local Development Setup

The repo is a uv workspace.

Root `pip install -e .` was incorrect because the root `pyproject.toml` has:

```text
[tool.uv]
package = false
```

and setuptools discovered multiple top-level packages.

Correct setup:

```powershell
python -m pip install uv
uv sync
```

This successfully resolved and installed the workspace.

---

# 23. Dependency Fixes Made

`apps/api/pyproject.toml` originally referenced workspace packages using relative file paths:

```text
xymphony-contracts @ file:packages/contracts
xymphony-realtime @ file:packages/realtime
```

Those paths were incorrect when resolved from the package directory.

They were changed to workspace dependencies:

```text
xymphony-contracts
xymphony-realtime
```

Similarly:

`packages/realtime/pyproject.toml`

was changed from:

```text
xymphony-contracts @ file:packages/contracts
```

to:

```text
xymphony-contracts
```

`uv sync` then succeeded.

These changes were local dashboard-development setup changes and were not part of the frontend feature itself.

---

# 24. API / PostgreSQL Setup

The API is run with:

```powershell
uv run uvicorn xymphony_api.main:app --app-dir apps/api/src --port 8000
```

Do NOT use `--reload` currently because WatchFiles was monitoring `.venv` files and caused reload loops.

The API is working.

Health test:

```powershell
Invoke-WebRequest http://127.0.0.1:8000/v1/health -UseBasicParsing -TimeoutSec 5
```

Successful response:

```json
{
  "status": "ok",
  "database": "connected"
}
```

Agents test:

```powershell
Invoke-WebRequest http://127.0.0.1:8000/v1/projects/00000000-0000-4000-8000-000000000002/agents -UseBasicParsing -TimeoutSec 10
```

Successful response:

```json
{
  "items": [],
  "next_cursor": null
}
```

This confirms:

- API works
- PostgreSQL works
- Project exists
- Agent route works
- There are currently no agents

---

# 25. Docker Issue Resolved

Initially:

```text
Test-NetConnection localhost -Port 5432
```

returned:

```text
TcpTestSucceeded : False
```

because Docker Desktop was not running.

Docker Compose initially failed because the Docker engine pipe was unavailable.

After Docker was started, PostgreSQL became available and the API health endpoint reported:

```json
{
  "status": "ok",
  "database": "connected"
}
```

---

# 26. Alembic

The attempted command:

```powershell
uv run alembic -c apps/api/alembic.ini upgrade head
```

failed because the command was being run from the repository root while Alembic expected the local API directory.

The correct approach is:

```powershell
cd apps\api
uv run alembic upgrade head
```

Do NOT run `alembic init`.

The repository already contains:

```text
apps/api/alembic
apps/api/alembic.ini
```

---

# 27. Current Immediate Next Step

Before implementing the Agent Builder, inspect the existing dashboard route structure.

Run:

```powershell
Get-ChildItem -Recurse -File apps\dashboard\app\agents
```

The goal is to determine exactly what currently exists under:

```text
apps/dashboard/app/agents
```

especially whether an existing route already exists for:

```text
/agents/[id]/overview
```

Then implement the builder **file by file**, reusing the existing dashboard shell and backend contracts.

Do not jump directly into implementation before inspecting the current route structure.

---

# 28. Important Product / Engineering Rules

1. **Source code is the implementation source of truth.**
2. The context markdown is the historical/architectural source of truth.
3. If source and context conflict, trust the current source.
4. Inspect existing files before creating new architecture.
5. Reuse established abstractions.
6. Keep changes focused.
7. Do not modify runtime internals for dashboard features unless necessary and coordinated.
8. Do not invent API fields that the backend does not expose.
9. Do not expose provider secrets in the frontend.
10. Do not pretend unsupported providers are available.
11. Do not prematurely add infrastructure.
12. Do not create fake placeholder architecture just to match the future monorepo layout.
13. Test before committing.
14. Follow the Person 2 branch workflow.
15. Person 2 should not push directly to `main`.

---

# 29. Git Checkpoint Rule

At each meaningful checkpoint:

- Determine whether Git work is needed.
- State the branch.
- Give exact commands.
- Explain why the checkpoint is being made.
- Do not assume a commit should happen if the code is not tested.
- Do not silently tell the user to commit broken or incomplete work.

Current branch:

```text
person2/dashboard
```

---

# 30. Current State at the End of This Chat

The project is in a good working state.

### Backend

Working:

- PostgreSQL
- FastAPI
- Health endpoint
- Agents endpoint
- Agent creation endpoint
- AgentVersion API
- Existing runtime/provider architecture

### Frontend

Working:

- Next.js dashboard
- Dashboard shell
- Overview
- Agents list
- Create Agent screen
- API integration for listing/creating agents

### Current task

Continue building the **Agent Builder / Agent Overview**.

First command to run:

```powershell
Get-ChildItem -Recurse -File apps\dashboard\app\agents
```

Then inspect the existing route structure and implement the builder without inventing unsupported backend functionality.

