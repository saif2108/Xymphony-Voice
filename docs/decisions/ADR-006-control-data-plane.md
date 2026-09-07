# ADR-006: Control plane / data plane separation

- **Status:** Accepted  
- **Date:** 2026-09-07  

## Context

Builders edit prompts while users talk. Realtime loops are latency- and cancellation-sensitive. CRUD is consistency- and authz-sensitive.

## Problem

How does configuration reach execution without live-editing a call or blocking TTS on ORM locks?

## Decision

**Control plane:** FastAPI + dashboard. PostgreSQL source of truth for config. Publish/freeze **AgentVersion**.

**Data plane:** runtime-worker. Loads **immutable snapshot** at session start. Pins `agent_version_id` + `config_hash` on Session. Ignores later publishes.

Playground “apply changes” = **new session**.

Worker is a separate process from `apps/api`.

## Alternatives

| Alternative | Why not |
| --- | --- |
| Runtime reads `agents` row every turn | Mid-call prompt swap, extra RTT, lock contention |
| Everything in Next.js serverless | Cold start + streaming + WS to vendors is hostile |
| One process “for P1 speed” | Acceptable only as a **temporary** Compose merge if documented; default is split so we do not teach the wrong boundary |

## Tradeoffs

- **+** Correct versioning, scale workers independently  
- **−** Snapshot fetch is a session-start dependency (timeout + fail session)  
- **−** Two deploys in Compose  

## Consequences

See [architecture.md](../architecture.md) §5. Internal snapshot API or shared-read DB.

## Reconsider if

Edge runtime must run in-browser (unlikely) or we need a third **edge config CDN** at huge scale — still snapshots, not live rows.
