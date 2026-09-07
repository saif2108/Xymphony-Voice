# ADR-007: ARQ on Redis for async jobs

- **Status:** Accepted  
- **Date:** 2026-09-07  

## Context

Ingest, embeddings, evaluation, retention deletes must not run on the API request thread or the voice event loop. Redis is already planned.

## Problem

Which Python worker?

## Decision

**ARQ** (asyncio Redis queue) for job execution.

Fits FastAPI/asyncio, uses Redis we already run, small ops footprint. Celery is the scale-up path.

**Not in P1** unless we add uploads. Compose service `arq-worker` arrives with RAG.

## Alternatives

| Alternative | Tradeoff |
| --- | --- |
| Celery | Mature, heavier, historically sync-first |
| Dramatiq | Solid; less asyncio-native than ARQ |
| Temporal | Durable workflows overkill NOW |
| FastAPI BackgroundTasks | No retry/visibility; rejected for ingest |
| RQ | Fine but ARQ matches asyncio |

## Tradeoffs

- **+** Simple, Redis-only  
- **−** Less ecosystem than Celery; weaker delayed-cron story — use ARQ cron or a tiny scheduler  
- **−** Redis downtime pauses jobs (config still in Postgres)  

## Reconsider if

We need multi-queue fairness, beat-style complex schedules, or exactly-once across regions — then Celery or Temporal. LangGraph checkpointing does **not** replace ARQ for file ingest.
