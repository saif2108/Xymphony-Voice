# RAG / Knowledge Design

**Status:** Phase 0. **Not in Prototype 1.** Horizon: **NEAR**.  
**Vector:** PostgreSQL + pgvector initially ([ADR-003](decisions/ADR-003-postgres-pgvector.md)).  
**Knowledge is not memory.** [memory-design.md](memory-design.md)

---

## 1. Objects

```
KnowledgeSource → Document → Chunk → Embedding (on chunk)
Retriever → RetrievalResult → (prompt injection + citations)
```

---

## 2. Pipeline

```
Upload (dashboard)
  → object storage (S3/MinIO)
  → ARQ job: parse → normalize → chunk → embed → upsert VectorStore
  → document.status=ready
Turn (runtime)
  → Retriever(query=user transcript, filters=tenant+bindings)
  → optional rerank (LATER)
  → inject bounded context into LLM messages
  → emit RetrievalResult event (chunk ids, not raw dump in UI if PII policy)
```

**Chunking (proposed):** recursive character / sentence, **400–800 tokens**, **50–100 overlap**, TBD per eval.

---

## 3. Isolation and ACL

- Every chunk row has `organization_id`, `project_id`.  
- Retriever **requires** those filters plus `knowledge_source_id IN agent_version.bindings`.  
- No “search all org knowledge” unless an AgentVersion explicitly binds those sources.

---

## 4. Citations

Inspector shows document title + span. User-facing citations optional per AgentVersion flag.

---

## 5. Versioning and deletion

New file version → new `documents.version_n` → re-chunk → delete old chunk ids.  
Delete source → delete chunks + object (retention job).  
GDPR-ish delete: by document id; sessions that already cited remain with id tombstone.

---

## 6. Failure

Embed timeout → job retry 3x then `document.status=failed`.  
Retrieve timeout → turn continues **without** knowledge; `Error` `retrieval_failed` (retryable); do not hallucinate “according to the manual” without chunks — **guardrail** NEAR.

---

## 7. Replace vector store

`VectorStore` port. pgvector NOW because ops is one database. Revisit if query latency or scale exceeds Postgres comfort (approx millions of chunks / noisy neighbor) — see ADR-003.

---

## 8. Tests

Tenant leak test (must fail closed). Empty corpus. Bindings respected.
