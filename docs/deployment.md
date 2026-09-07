# Deployment

**Status:** Phase 0. **P1 target:** Docker Compose on one machine. **Not Kubernetes.**

---

## 1. Environments

| Env | NOW | Later |
| --- | --- | --- |
| Laptop Compose | Yes | Yes |
| Single VM Compose/systemd | Possible | Staging |
| Kubernetes | No | When ops pain is real |

---

## 2. Compose services (Phase 1+)

`dashboard`, `api`, `runtime-worker`, `arq-worker` (NEAR), `postgres`, `redis`, `minio` (NEAR), `livekit`, optionally `caddy`.

LiveKit Cloud is an allowed alternative to local LiveKit **if** the MediaTransport adapter remains the only coupling ([ADR-001](decisions/ADR-001-use-livekit.md)).

---

## 3. Product deployment channels (agents)

| Channel | Horizon |
| --- | --- |
| Playground (browser) | NOW |
| Web embed | LATER |
| Public API / SDK | LATER |
| Mobile | VISION |
| Telephony SIP/PSTN | VISION |

Architecture: Channel is a field on Deployment/Session, not a fork of the runtime. Telephony will be another MediaTransport adapter, not a new agent model.

---

## 4. Config change vs live sessions

Deployments point at AgentVersion. Active sessions pinned. Rollback = move pointer; old calls finish on old snapshot.

Shadow **LATER:** duplicate events to a shadow version without user audio out.

---

## 5. Self-host / hybrid (VISION)

Same Compose/Helm **later**. Requirements: BYO keys, no mandatory Xymphony cloud. Do not encode cloud-only APIs in contracts.

---

## 6. Async jobs

**Choice: ARQ + Redis** ([ADR-007](decisions/ADR-007-async-jobs.md)). Ingest, embed, eval, retention deletes.

---

## 7. Scale

Add `runtime-worker` replicas; LiveKit assigns jobs. Postgres primary. Redis. No Kafka NOW.

---

## 8. Failure

Compose restart: in-memory sessions die (P1 acceptable). LATER: resume from Postgres transcript.
