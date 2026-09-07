# Data Model

**Status:** Phase 1 Step 2 — Alembic migration `0001_p1_control_plane` implements organizations, projects, agents, and agent_versions. Remaining P1 tables (sessions, turns, messages) are not created yet.  
**Terms:** [glossary.md](glossary.md)

---

## 1. Tenancy

Every tenant table includes `organization_id`. Project-scoped tables also include `project_id`.

**Queries always filter both.** Runtime snapshot includes these IDs so events inherit them.

**NOW:** one Organization ↔ one Workspace UX. No `workspaces` table.

---

## 2. Entity relationship (logical)

```
users
  └── memberships ── organizations
                        └── projects
                              ├── agents ── agent_versions
                              │                 ▲
                              │                 │
                              ├── deployments ──┘
                              │       └── sessions ── turns ── messages
                              │                         └── events (optional table or JSONB)
                              ├── tools ── tool_versions
                              ├── workflows ── workflow_versions
                              ├── knowledge_sources ── documents ── document_chunks
                              ├── evaluations ── evaluation_runs
                              └── api_keys

organizations ── provider_configs
organizations ── audit_logs
```

AgentVersion **references** tool_versions, knowledge_sources, workflow_versions by ID lists / FK — not by copying secrets.

---

## 3. Core tables

### users

`id, email unique, name, status, created_at, updated_at`  
Auth subject id if using external IdP: `idp, idp_subject` unique.

### organizations

`id, name, slug unique, plan, retention_days (proposed default 30, TBD), created_at`

### memberships

`id, organization_id, user_id, role (owner|admin|developer|viewer), unique(organization_id, user_id)`

### projects

`id, organization_id, name, slug, created_at, unique(organization_id, slug)`

### agents

`id, organization_id, project_id, name, description, status (draft|active|archived), created_by, created_at, updated_at`  
**Mutable:** name, description, status, tags.  
**Not stored here:** instructions, models.

### agent_versions

`id, organization_id, project_id, agent_id, version_n int, status (draft|published|deprecated),`  
`instructions, personality, goals jsonb, constraints jsonb, locale,`  
`llm jsonb, stt jsonb, tts jsonb,`  -- {provider_key, model_or_voice, params} **no secrets**  
`tool_version_ids uuid[], knowledge_source_ids uuid[], workflow_version_id uuid null,`  
`memory_policy jsonb, guardrails jsonb, escalation_policy jsonb,`  
`config_hash, created_by, created_at, published_at`  
`unique(agent_id, version_n)`

**Immutable** once `status=published`. Draft rows may PATCH. Publish copies-on-write if needed (either freeze in place or clone — **decision:** freeze in place; further edits increment `version_n`).

### deployments

`id, organization_id, project_id, agent_id, agent_version_id, environment, channel, status, traffic_percent default 100, created_at`  
**NEAR/LATER.** P1 playground skips this table and sets `sessions.deployment_id` null + `agent_version_id` directly.

### sessions

`id, organization_id, project_id, agent_id, agent_version_id, deployment_id null,`  
`status, channel, livekit_room, config_hash,`  
`started_at, ended_at, end_reason,`  
`usage jsonb, error_code null`  
Indexes: `(organization_id, project_id, started_at desc)`, `agent_id`.

### turns

`id, session_id, organization_id, sequence, status (in_progress|committed|cancelled|failed), started_at, ended_at, interrupted bool`

### messages

`id, session_id, turn_id, organization_id, role (user|assistant|system|tool), status (committed|interrupted),`  
`parts jsonb,  -- ContentPart[]`  
`created_at`  
Index: `(session_id, created_at)`.

### events

`id, session_id, organization_id, sequence, type, envelope jsonb, created_at`  
`unique(session_id, sequence)`  
P1: persist subset (see [event-model.md](event-model.md)). Partition **LATER**.

---

## 4. Tools, workflows, knowledge (NEAR+)

### tools / tool_versions

Tool: identity (`name`, `project_id`). Version: `kind (http|webhook|mcp|python|graphql|internal)`, `input_schema`, `output_schema`, `timeout_ms`, `retry_policy`, `idempotency`, `side_effect_class (read|write)`, `auth_ref` (pointer to secret, not secret), `permissions jsonb`.

### workflows / workflow_versions

`graph jsonb` (nodes, edges), `status draft|published`. Immutable when published.

### knowledge_sources

`id, project_id, name, type (upload|url|connector)`

### documents

`id, knowledge_source_id, object_key, mime, status (pending|ready|failed), version_n, created_at`

### document_chunks

`id, document_id, organization_id, project_id, ordinal, text, embedding vector, metadata jsonb`  
Index: ivfflat/hnsw on embedding **and** btree `(organization_id, project_id)`.

Deletion: delete chunks then object; re-index job on document version bump.

---

## 5. Eval, keys, secrets, audit

### evaluations / evaluation_runs / scenarios / scores (LATER)

Dataset in object storage; rows reference `object_key`. Runs point at `agent_version_id`.

### api_keys

`id, organization_id, project_id, prefix, hash, scopes[], created_by, last_used_at, revoked_at`  
Store **only hashes** (argon2/bcrypt). Prefix for display.

### provider_configs

`id, organization_id, provider_key, encrypted_payload, kms_key_id?, created_at`  
Runtime decrypts in worker memory. Never write decrypted values to `agent_versions` or logs.

### audit_logs

`id, organization_id, actor_user_id, action, resource_type, resource_id, at, ip, metadata`  
Control-plane mutations + tool writes (**NEAR**).

---

## 6. Indexes (beyond PKs/FKs)

- `memberships (user_id)`  
- `agents (project_id, status)`  
- `agent_versions (agent_id, version_n desc)`  
- `sessions (organization_id, started_at desc)`  
- `messages (session_id, created_at)`  
- `document_chunks` vector index + tenant btree  
- `audit_logs (organization_id, at desc)`

---

## 7. What goes where

| Data | PostgreSQL | Redis | Object storage |
| --- | --- | --- | --- |
| Config, users, versions | Yes | cache optional | no |
| Transcript | Yes | no | optional recording |
| Hot session FSM | no | yes | no |
| Rate limits | no | yes | no |
| ARQ jobs | no | yes | no |
| PDF originals | metadata | no | yes |
| Eval datasets | metadata | no | yes |
| Embeddings | pgvector NOW | no | no |

---

## 8. Agent vs Version vs Deployment vs Session (data)

| Entity | Cardinality | Mutability |
| --- | --- | --- |
| Agent | 1 identity | metadata |
| AgentVersion | N per agent | draft then freeze |
| Deployment | N bindings | pointer change = new sessions |
| Session | N executions | append-only messages |

---

## 9. P1 subset

**Required tables:** users, organizations, memberships, projects, agents, agent_versions, provider_configs, sessions, turns, messages.  
**Recommended:** events.  
**Defer:** deployments, tools, workflows, knowledge, eval, api_keys (unless auth needs them).

---

## 10. ORM / migrations

**Phase 1:** Alembic + SQLAlchemy or Prisma-like — **decision:** SQLAlchemy 2 + Alembic in `apps/api`, shared models importable by worker **or** worker reads via internal HTTP. **Preferred:** shared `packages/contracts` Pydantic + API as source; worker fetches snapshot over internal authenticated GET to avoid dual-writers.

**Single writer for config:** control plane only. **Session row:** control plane inserts on `POST /sessions`. **Runtime:** updates session status/usage; inserts turns, messages, events.
