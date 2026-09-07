# Memory Design

**Status:** Phase 0. **P1 uses conversation state only** (message list). Do not collapse RAG into “memory.”

---

## 1. Six distinct stores

| Kind | Lifetime | Store | Who writes | P1 |
| --- | --- | --- | --- | --- |
| **Conversation state** | Session | Process + Redis | Runtime | Yes (process) |
| **Short-term memory** | Session / few sessions | Postgres summary | Runtime summarizer | LATER |
| **Long-term memory** | Durable facts | Postgres | Extractor job + approval **VISION** | VISION |
| **User memory** | Per caller identity | Postgres | Extractor | LATER |
| **Agent memory** | Per agent | Postgres | Restricted | VISION |
| **Knowledge** | Corpus | pgvector | Ingest | NEAR |

---

## 2. Policies (AgentVersion.memory_policy)

- `summarize_after_turns` (proposed 20)  
- `persist_user_memory: bool`  
- `redact_pii: bool`  
- `ttl_days`

Runtime **loads** memory as messages or a system appendix. Runtime **never** uses LLM as the only copy of a fact that tools already store (orders live in the order API).

---

## 3. Extraction (LATER)

Async job: read transcript → structured facts JSON → validate → upsert. User-facing “what we remember” UI with delete.

---

## 4. Risks

Prompt injection writing long-term memory → require allowlisted extract schema + human/policy gate for write memories.

---

## 5. Intentionally not building

A single `memory` embedding dump of the whole chat as RAG replacement for instructions.
