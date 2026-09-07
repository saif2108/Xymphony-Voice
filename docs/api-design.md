# API Design — Control Plane

**Status:** Phase 1 Step 2 implemented `GET /v1/health` and Agent/AgentVersion CRUD under `/v1/projects/{pid}`. Auth, sessions, and realtime endpoints are not implemented.  
**Base path:** `/v1`  
**Auth:** session cookie or bearer JWT for humans; API keys **LATER**. Runtime worker uses a **service credential**, not a user cookie.

Realtime media is **not** JSON audio. Session establishment is REST; media is LiveKit.

---

## 1. Principles

- Validate all bodies with Pydantic; reject unknown fields in strict mode for write endpoints.  
- Tenancy from auth context, **not** from client-supplied org override (except superadmin, which we do not have).  
- Pagination: cursor `?cursor=&limit=` default 20 max 100.  
- Errors: `{code, message, details?, request_id}` + HTTP status.  
- Idempotency: `Idempotency-Key` header on creates (sessions, publishes) **NEAR**; P1 nice-to-have for `POST /sessions`.  
- Versioning: URL `/v1`; breaking changes → `/v2`. Additive fields OK.

---

## 2. AuthN / AuthZ

| Mechanism | Use |
| --- | --- |
| Session/JWT | Dashboard |
| API key `xy_…` | SDK **LATER** |
| Worker service token | Snapshot fetch, session writes |

AuthZ: role from membership. P1: only `owner` exists but checks still go through a `require_project_access(project_id)` function.

---

## 3. Resource map

| Prefix | NOW | Notes |
| --- | --- | --- |
| `/v1/health` | Yes | liveness |
| `/v1/auth/*` | Yes | login/signup/logout as chosen IdP |
| `/v1/projects` | Yes | |
| `/v1/projects/{pid}/agents` | Yes | |
| `/v1/projects/{pid}/agents/{aid}/versions` | Yes | |
| `/v1/projects/{pid}/sessions` | Yes | create + get + messages |
| `/v1/projects/{pid}/sessions/{sid}/token` | Yes | LiveKit JWT for client |
| `/v1/internal/agent-versions/{vid}/snapshot` | Yes | worker only |
| `/v1/projects/{pid}/tools` | NEAR | |
| `/v1/projects/{pid}/knowledge` | NEAR | |
| `/v1/projects/{pid}/workflows` | LATER | |
| `/v1/projects/{pid}/deployments` | LATER | |
| `/v1/projects/{pid}/evaluations` | LATER | |
| `/v1/projects/{pid}/analytics` | NEAR | |
| `/v1/api-keys` | LATER | |
| `/v1/provider-configs` | Yes | org-level secrets |

Realtime events to UI: **SSE or WebSocket** `GET /v1/projects/{pid}/sessions/{sid}/events` (authz). Not LiveKit data channel as the only inspector path (may duplicate **NEAR**).

---

## 4. Session establishment (P1)

```
POST /v1/projects/{pid}/agents/{aid}/sessions
  body: { agent_version_id? }  # default latest draft
  → { session_id, livekit: { url, room, token } }

Client connects WebRTC to LiveKit with token.
Worker receives LiveKit job with session_id.
```

**Authorization:** user must be member; agent in project.  
**Worker path:** LiveKit dispatches job → worker `GET snapshot` → run.

Do **not** send provider secrets to the browser.

---

## 5. Agent CRUD (P1)

```
POST   /v1/projects/{pid}/agents
PATCH  /v1/projects/{pid}/agents/{aid}
GET    /v1/projects/{pid}/agents
GET    /v1/projects/{pid}/agents/{aid}
POST   /v1/projects/{pid}/agents/{aid}/versions
PATCH  /v1/projects/{pid}/agents/{aid}/versions/{vid}   # draft only
GET    /v1/projects/{pid}/agents/{aid}/versions
```

Publish: `POST .../versions/{vid}/publish` **NEAR**.

---

## 6. Error codes (stable strings)

`unauthorized`, `forbidden`, `not_found`, `validation_error`, `conflict_published_immutable`, `provider_not_configured`, `rate_limited`, `internal`.

---

## 7. Filtering

List sessions: `?agent_id=&status=&from=&to=`. Never unscoped list across orgs.

---

## 8. SDK relationship (LATER)

The SDK is a typed client of `/v1`. It does not embed runtime. Methods: create/update/publish agent, create session, send text message, upload knowledge, run evaluation, fetch traces. Voice in apps uses LiveKit token from API then vendor SDK or LiveKit client.

---

## 9. Rate limiting

Redis token bucket: per user and per org. Proposed P1: 60 req/min mutating, 30 session creates/hour/org (**TBD**). Worker internal API not user-limited but IP-allow or mTLS **LATER**; P1: shared secret.

---

## 10. Testing

OpenAPI generated from FastAPI. Contract tests for 401/403 isolation. No “success without org filter.”
