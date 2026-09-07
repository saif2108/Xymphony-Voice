# ADR-004: Event-driven agent runtime

- **Status:** Accepted  
- **Date:** 2026-09-07  

## Context

Voice is concurrent: VAD, STT partials, LLM tokens, TTS frames, user barge-in. A naive call chain (`stt() then llm() then tts()`) cannot cancel cleanly or explain itself.

## Problem

How do we order work, cancel, persist inspector data, and extend to text/tools/multi-agent without a second architecture?

## Decision

Internal **event/frame** model with a canonical envelope ([event-model.md](../event-model.md)). Per-session **single applicator** loop, monotonic `sequence`, `turn_id` cancellation, ignore stale events.

Events are conceptual contracts, not “Kafka required.” **P1 bus = in-process asyncio queue.** Persist a subset to Postgres. Redis pub/sub for UI.

Not a distributed event mesh.

## Alternatives

| Alternative | Why not |
| --- | --- |
| Synchronous pipeline only | Barge-in becomes hacks |
| NATS/Kafka now | Ops without benefit at 5 sessions |
| LiveKit data messages as sole event log | Couples inspector to transport |

## Tradeoffs

- **+** Testable interrupt; inspector; multimodal extension  
- **−** Must discipline sequence assignment  
- **−** Risk of over-persisting token spam — policy in event-model.md  

## Consequences

Runtime tests inject events. UI brain consumes events, not CoT.

## Reconsider if

We need cross-region session failover — then persist events as the log **before** introducing a broker.
