# Security Architecture

**Status:** Phase 0. Mechanisms below are **design requirements**, not implemented controls.  
**P1 minimum:** FR-SEC-001, 002, 004 — auth, tenancy columns, encrypted provider secrets.

This is not “use best practices.” Each row is a mechanism.

---

## 1. Authentication

| Actor | Mechanism |
| --- | --- |
| Human (dashboard) | IdP or first-party session; HTTP-only Secure cookies; CSRF on cookie auth |
| SDK **LATER** | API key `xy_` + hash lookup; optional rotation |
| Runtime worker | Service token (HMAC or JWT with `role=worker`); not a user JWT |

Passwords if first-party: argon2id. No session tokens in logs.

**P1 choice deferred** (Clerk vs first-party) — both must sit behind `IdentityProvider` so we can swap. See phase-0-review.

---

## 2. Authorization / RBAC

Roles on `memberships`:

| Role | Control plane | Data plane sessions |
| --- | --- | --- |
| owner | all | all in org |
| admin | all except billing **LATER** | all |
| developer | mutate agents/tools/knowledge in project | playground + inspect |
| viewer | read | inspect |

**NOW:** implement `require_project_access`; P1 may only mint owner. Still deny cross-org ids.

Project-level roles **LATER** if needed. Default: org role applies to all projects.

---

## 3. Tenant isolation

- Every SELECT/UPDATE includes `organization_id` from auth context.  
- Application tests: user A token + user B resource UUID → 404 (not 403) to reduce enumeration **proposed**.  
- pgvector queries **must** include tenant filters (defense in depth: RLS **LATER** when we have time; **NEAR** recommended).  
- Object keys prefixed `org/{organization_id}/project/{project_id}/...`.

---

## 4. Secrets

| Secret | Storage | Runtime access |
| --- | --- | --- |
| Provider API keys | `provider_configs.encrypted_payload` (Fernet/AES-GCM with `APP_MASTER_KEY` NOW; KMS **LATER**) | Worker decrypt once per session |
| DB URL | env | processes |
| LiveKit keys | env / provider_configs | API mints room tokens; client gets **room-scoped** JWT only |

Never: secrets in AgentVersion JSON, git, client bundles, OTel attributes, LLM prompts.

---

## 5. API keys (LATER)

Generate 32+ bytes; store hash; show once. Scopes: `agents:read`, `sessions:create`, etc. Revoke sets `revoked_at`.

---

## 6. Tool security (NEAR)

- Host allowlist, scheme https only by default  
- Block 10.0.0.0/8, 127.0.0.0/8, 169.254.0.0/16, metadata IPs  
- Max response size **proposed 1MB**  
- Timeouts  
- Signed webhooks inbound: HMAC + timestamp (skew **300s**) + nonce replay cache in Redis  
- MCP: pin identity; do not auto-trust new tools from a server without bind step  

Python tools: separate process, no raw SQL string concat.

---

## 7. Prompt / tool injection

Assume **all retrieved documents and user speech are adversarial**.

Mechanisms:

- Delimit untrusted content in prompt (`<<untrusted user>>`)  
- Tools: no generic `http_fetch(url)`  
- Ignore model-requested tools not in allowlist  
- Knowledge: sanitize downloaded HTML; no instruction-like auto-exec  
- “Why” UI never shows system secrets  

---

## 8. Rate limiting and abuse

Redis counters: login, session create, STT minutes **NEAR**. P1: coarse per-org session cap. Audio bombs: max session duration, max bitrate via LiveKit.

---

## 9. PII, transcripts, retention

- Transcripts are **sensitive by default**  
- Encryption at rest: disk/Postgres (cloud) + TLS in transit  
- `organizations.retention_days` job deletes sessions/messages/events/recordings  
- Recordings **opt-in** AgentVersion flag; object storage private  
- Access: RBAC + audit `transcript.read` **LATER**

---

## 10. Knowledge ACL

Bind sources per AgentVersion. No global search. Delete propagates to chunks.

---

## 11. Environment separation

`development` / `staging` / `production` **LATER**. P1: local Compose + `.env` not committed. Production credentials never in P1 playground defaults.

---

## 12. Audit

Control-plane writes → `audit_logs`. Tool `write` → audit + session event.

---

## 13. HITL / takeover (LATER)

Operator must be org member. Takeover is an authorization event.

---

## 14. Failure

Auth store down → control plane 503; existing worker sessions continue. Compromised worker token → rotate env, drain jobs.

---

## 15. Tests

Isolation, SSRF, immutable published version, secret redaction in logs (grep CI **NEAR**).
