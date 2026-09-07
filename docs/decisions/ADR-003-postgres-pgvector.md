# ADR-003: PostgreSQL + pgvector as initial system of record and vector store

- **Status:** Accepted  
- **Date:** 2026-09-07  

## Context

We need OLTP for tenancy/agents/sessions and vectors for RAG (**NEAR**). Two engineers cannot operate five data systems.

## Problem

Where do we store canonical config, transcripts, and embeddings without painting into a corner?

## Decision

**PostgreSQL** is the system of record. **pgvector** for embeddings initially. Redis is ephemeral (sessions hot state, pub/sub, rate limits, ARQ). S3/MinIO for blobs.

`VectorStore` port allows replacement.

## Alternatives

| Alternative | Why not now |
| --- | --- |
| Mongo as SoR | Weaker relational tenancy/constraints |
| Pinecone/Weaviate first | Extra bill + network hop; premature |
| SQLite | Poor concurrent workers |
| Redis as SoR | Persistence/durability lie |

## Tradeoffs

- **+** One backup story, joins for inspector, RLS later  
- **−** pgvector ops at huge scale (revisit at millions of chunks / p95 query pain)  
- **−** Embeddings bloat Postgres — acceptable until measured  

## Consequences

Alembic migrations. Chunk table includes tenant ids + vector index.

## Reconsider if

Vector p95 exceeds RAG latency budget after indexing/tuning; need hybrid search a specialist DB does better; compliance requires separate vector silo.
