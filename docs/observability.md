# Observability

**Status:** Phase 0. Standard: **OpenTelemetry** traces + metrics + logs.  
**P1:** structured JSON logs + spans for session/turn/stt/llm/tts/interrupt even if collector is local stdout.

---

## 1. Why more than logs

Realtime AI fails as **latency, cancellation, and partial streams**. Logs without `turn_id` are not operable.

---

## 2. Telemetry hierarchy

```
Organization → Project → Agent → AgentVersion → Deployment → Session → Turn → Event
```

Resource attributes on every span/metric: `org.id`, `project.id`, `agent.id`, `agent.version_id`, `deployment.id?`, `session.id`.

---

## 3. Trace shape

```
Session
├── transport.join
├── snapshot.load
├── STT (session-long or per-utterance)
├── Turn
│   ├── retrieve? 
│   ├── LLM
│   ├── Tool* 
│   ├── LLM
│   └── TTS
├── Interrupt (link to cancelled turn)
└── Session.end
```

Span events: barge-in, provider retry.

---

## 4. Metrics (names stable)

| Metric | Type | P1 |
| --- | --- | --- |
| `xymphony.sessions.active` | gauge | Yes |
| `xymphony.turn.e2e_ms` | histogram | Yes |
| `xymphony.llm.ttft_ms` | histogram | Yes |
| `xymphony.tts.ttfb_ms` | histogram | Yes |
| `xymphony.stt.final_ms` | histogram | Yes |
| `xymphony.interrupt.count` | counter | Yes |
| `xymphony.provider.errors` | counter | Yes |
| `xymphony.llm.tokens` | counter | Yes |
| `xymphony.cost.estimated_usd` | counter | NEAR |
| `xymphony.tool.latency_ms` | histogram | NEAR |
| `xymphony.retrieval.latency_ms` | histogram | NEAR |

---

## 5. Analytics product (NEAR/LATER)

Dashboard rollups: sessions, active, task success (**LATER** eval), containment, escalation, latency, cost, tokens, tool success, retrieval quality, error rate, interruption rate, provider health.

These read **metrics store / warehouse**, not OLTP scans of `events` at page load. P1: raw session list is enough.

---

## 6. Logs

JSON: `timestamp, level, msg, session_id, turn_id, correlation_id`.  
Forbidden: secrets, raw PCM, full card numbers (no vertical-specific scanners P1).

---

## 7. Failure of telemetry

OTel export fail → drop spans, **never** block TTS. Local logs still write.

---

## 8. Live Agent Brain

Subscribes to persisted/safe events. Same hierarchy. Not a second telemetry system.
