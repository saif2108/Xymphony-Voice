# Runtime Design — Xymphony Agent Runtime

**Status:** Phase 0 design. **No runtime code exists in this repository.**  
**Related:** [event-model.md](event-model.md) · [provider-interfaces.md](provider-interfaces.md) · [architecture.md](architecture.md) · [prototype-1.md](prototype-1.md)

The runtime is the **product**. LiveKit is **transport**. LLM/STT/TTS are **adapters**.

---

## 1. Purpose and boundaries

| This package owns | This package does not own |
| --- | --- |
| Session/turn lifecycle | Dashboard UI |
| Event loop, sequencing, cancellation | LiveKit server internals |
| Prompt compilation from AgentVersion snapshot | Mutating AgentVersion |
| Provider port invocation | Vendor-specific HTTP details (adapters) |
| Interruption / barge-in policy | Billing UI |
| Tool execution dispatch (**NEAR**) | Tool credential UX |
| Retrieval dispatch (**NEAR**) | Chunking pipeline (RAG package) |
| Workflow step dispatch (**LATER**) | React Flow editor |
| Emitting traces/metrics | Storing OTel long-term (collector) |

**Inputs:** AgentVersion snapshot, media frames, text frames, cancel signals.  
**Outputs:** TTS audio frames, transcript/events, persisted messages (via repository port), telemetry.  
**Depends on:** contracts, provider ports, optional tools/rag/workflow packages, Redis (ephemeral), Postgres repository port.  
**Dependents:** runtime-worker app, evaluation runner (**LATER**), simulation (**LATER**).

**Replaceability:** The worker host can change; the runtime library should remain hostable in a test harness with fake media.

---

## 2. Process architecture

**NOW:** one `runtime-worker` process per machine (Compose). It:

1. Authenticates to LiveKit as a worker  
2. Receives a job: `{session_id, room_name, agent_version_id, organization_id, project_id}`  
3. Loads snapshot from control-plane internal API or Postgres (service role)  
4. Instantiates `SessionController`  
5. Subscribes to participant audio; publishes agent audio  
6. Runs the event loop until terminal state  

Control plane **does not** run the voice loop in-process (keeps latency and GIL/blocking isolated; allows independent scale).

---

## 3. Lifecycles

### 3.1 Provider lifecycle

- Adapters created per session (or pooled HTTP clients process-wide).  
- `health()` optional; routing **LATER**.  
- On session end: `aclose()` — cancel HTTP, close WS to STT/TTS.

### 3.2 Session lifecycle

```
initializing → active → completed
                  ↘ failed
                  ↘ terminated
```

Barge-in does **not** change Session status. The Turn is `cancelled`; assistant Message may be `interrupted`. Session stays `active`.

| State | Meaning |
| --- | --- |
| `initializing` | Load snapshot, connect media, warm STT/TTS sockets if any |
| `active` | Conversation in progress (including during barge-in) |
| `completed` | User or agent ended cleanly |
| `failed` | Unrecoverable error |
| `terminated` | Explicit kill (admin, policy, shutdown) |

**Reconnect (LATER):** If the browser drops WebRTC but `session_id` + reconnect token is valid within `reconnect_ttl_sec` (**proposed default 60s, TBD**), attach a new participant to the same room/session. Ephemeral in-process state is lost if the worker died; **resume** then means: new worker loads transcript from Postgres and continues (no uncommitted turn). **NOW:** reconnect = new Session (document in UI).

**What survives a session:** messages, selected events, usage counters, status.  
**What does not:** cancellation tokens, audio jitter buffers, in-memory VAD, uncommitted partial LLM text (unless we persist interrupted assistant message — **yes, persist truncated assistant text actually played**).

**Termination:** client disconnect after grace period, max duration **proposed 30 min P1**, max turns **proposed 200**, explicit stop, fatal error.

### 3.3 Turn lifecycle

```
idle → user_speaking → user_finalizing → agent_thinking → agent_speaking → committed
                         ↓ barge-in                    ↓ barge-in
                      cancelled ←——————————————————————┘
```

A Turn has `turn_id` (UUID). All LLM/TTS work is tagged with `turn_id`. Cancellation is **turn-scoped**.

### 3.4 Event lifecycle

Produced → validated envelope → loop handler → side effects → optional persist → optional UI pub/sub.

Ordering: [event-model.md](event-model.md).

---

## 4. State

### 4.1 Ephemeral (process + Redis)

| Key | Where | Why |
| --- | --- | --- |
| Current `turn_id`, cancel token | Process | Latency |
| Sequence counter | Process (persist last seq occasionally) | Ordering |
| STT connection | Process | Streaming |
| Played-character cursor (for truncate) | Process | Interrupted assistant message |
| UI live events | Redis pub/sub | Dashboard |

Redis is **not** the agent config store.

### 4.2 Persistent (Postgres)

Session row, turns, messages, usage, terminal error code. Event bodies: **P1 recommended** persist `UserSpeech*`, `TranscriptFrame` (final), `Tool*`, `AgentInterrupted`, `Error`; drop raw `AudioFrame` and token spam or sample them.

### 4.3 Conversation state vs memory

P1 conversation state = message list + snapshot instructions. No long-term memory module.

---

## 5. Concurrency model

- **One asyncio task per Session** on the worker (P1).  
- Subtasks: STT reader, TTS writer, LLM stream, VAD.  
- **Single-threaded event applicator** per session: all mutations to session state go through the loop so barge-in cannot race prompt assembly.  
- Providers may run concurrently **only** when the loop schedules them (e.g. **NEAR** parallel retrieve + classification if policy allows).  
- **No shared mutable AgentVersion** across sessions without copy.

**Backpressure:** if TTS consumer is slow, pause LLM token → TTS enqueue at `max_tts_queue_chars` (**proposed 2k, TBD**). If STT backlog exceeds N frames, drop **oldest non-final** partials; never drop finals.

---

## 6. Streaming

| Stage | Streaming? | Chunking |
| --- | --- | --- |
| Mic → LiveKit | Yes | RTP frames |
| STT | Yes | Partials + finals |
| LLM | Yes | Tokens |
| TTS | Yes | Audio frames after **sentence/clause split** |
| UI transcript | Yes | Partials |

**Sentence-level TTS:** accumulate tokens until punctuation or pause heuristic (**proposed: `.?!` or 80 chars**), then `speak(chunk)` overlapping next LLM tokens. This is the primary TTFA optimization.

**Speculative work (NEAR, opt-in):** start TTS on first clause before full LLM completion. **Do not** speculate tool calls with side effects.

---

## 7. Interruption / barge-in (normative)

This section is the spec. Tests must encode it.

### 7.1 Happy interrupt

Agent Turn `T_a` is `agent_speaking`. User starts speaking.

1. VAD or STT emits `UserSpeechStarted` with `sequence=S`, `turn_id=T_u` (new turn created immediately).  
2. Loop sets `cancelled_turn_ids += {T_a}` and cancels `CancelToken` for `T_a`.  
3. **TTS:** stop synthesis; clear outbound audio queue; call adapter `cancel()`; stop publishing frames (flush already-in-RTP is tolerated; **no new** frames with `turn_id=T_a`).  
4. **LLM:** cancel HTTP/stream; ignore further tokens.  
5. Emit `AgentInterrupted` `{interrupted_turn_id: T_a, reason: "user_speech", played_text, unplayed_text}`.  
6. Persist assistant `Message` with `status=interrupted` and `content=played_text` (what the user likely heard). Discard unplayed text from the **durable** transcript (keep in event metadata for debug).  
7. **Tools (NEAR):** if a tool for `T_a` is in-flight:  
   - if not started HTTP: do not send  
   - if running: attempt cancel; on completion **after** cancel, **do not** feed result to LLM; persist `ToolResult` `{status: cancelled_or_unknown}`  
   - if completed before cancel: result is **committed** (side effects may have happened); include in history  
8. STT continues; on `UserSpeechEnded` + final transcript, start `T_u` agent work with history including interrupted assistant message.  
9. Respond.

### 7.2 Cancellation propagation

```
UserSpeechStarted
  → SessionController.cancel_turn(T_a)
      → llm_stream.aclose()
      → tts_stream.aclose()
      → outbound_audio.clear()
      → ignore predicate: event.turn_id in cancelled OR event.sequence < interrupt_seq
```

**Ignore predicate (stale events):** Drop `LLMToken`, `LLMResponse`, `TTSChunk` if `turn_id ∈ cancelled_turn_ids` OR `causation_id` chain points at cancelled turn.

### 7.3 Races

| Race | Handling |
| --- | --- |
| TTS chunk after cancel | Drop via ignore predicate |
| Final LLM response after cancel | Drop; do not persist as committed assistant |
| UserSpeechStarted false VAD blip | Require min speech ms **proposed 150–250ms** or STT confidence; else `false_interrupt` metric, resume TTS **only if** we paused speculatively — **P1: do not resume paused TTS; treat as interrupt** (simpler, slightly worse UX) |
| Two UserSpeechStarted | Idempotent: one `T_u` |
| Tool completes after new turn started | Do not inject into new turn; store orphan result on old turn |
| User interrupts during `agent_thinking` (no audio yet) | Cancel LLM; no assistant message or empty interrupted |

### 7.4 State consistency

History for the next LLM call:

```
[system from snapshot]
[prior committed messages]
[assistant interrupted: played_text]
[user: new transcript]
```

Do not keep cancelled tokens in the prompt.

### 7.5 Event ordering

Monotonic `sequence` per session. `UserSpeechStarted` sequence is the interrupt barrier. See [event-model.md](event-model.md).

---

## 8. Timeouts, retries, idempotency

Proposed defaults (TBD by measurement):

| Operation | Timeout | Retry |
| --- | --- | --- |
| Snapshot fetch | 2s | 2x |
| STT connect | 3s | 1x then fail session |
| LLM first token | 8s | 0 on streamed cancel; 1x if connection error before tokens and turn not cancelled |
| LLM total | 60s | no |
| TTS first byte | 5s | 1x connection error |
| Tool (**NEAR**) | per-tool, default 10s | per-tool idempotent only |
| Session max | 30 min | — |

**Retries:** only **safe** (idempotent, no duplicate side effects). LLM retries must use same `idempotency_key=turn_id` if the adapter supports it; otherwise only retry before first token.

**Idempotency:** `turn_id` + `tool_call_id` unique. Duplicate `ToolCall` events with same id are no-ops.

---

## 9. Provider failure

| Failure | Behavior |
| --- | --- |
| STT disconnect mid-session | Reconnect once; else `Error` `stt_failed`, session `failed`, UI message |
| LLM 429 | `Error` `llm_rate_limited`; optional one retry after `Retry-After` if still same turn |
| LLM 5xx | One retry if no tokens; then fail turn with spoken apology **from a local fallback template** (not a second model in P1) |
| TTS fail after text exists | Fallback: show text in UI; optional Piper if configured; else speak nothing + error |
| LiveKit disconnect | Wait reconnect_ttl; else terminate |

**Fallback model routing:** LATER. P1: single model from snapshot.

---

## 10. Graceful shutdown

Worker receives SIGTERM:

1. Stop accepting new LiveKit jobs  
2. For each session: emit `Error` `worker_draining` or complete current TTS clause, then terminate  
3. Flush traces/messages (timeout **proposed 5s**)  
4. Exit  

Resource cleanup: cancel tasks, close WS, release Redis keys `session:{id}:*`.

---

## 11. Layer boundaries

```
realtime/          MediaTransport: tracks in/out, room join
agent-runtime/     SessionController, TurnMachine, PromptCompiler, Interruptor
providers/         adapters
tools/             ToolExecutor (NEAR)
rag/               KnowledgeRetriever (NEAR)
memory/            MemoryStore (LATER)
workflows/         WorkflowExecutor (LATER)
```

**Rule:** `agent-runtime` imports ports from `contracts`, not `openai`/`elevenlabs` packages.

---

## 12. Latency budget (proposed)

```
user speech end
  → VAD/endpoint     200–400 ms     (endpointing, not RTT)
  → STT final        100–400 ms     (streaming already running)
  → runtime assemble  5–20 ms
  → retrieval (NEAR)  50–200 ms     (parallelize later)
  → LLM TTFT         200–600 ms
  → TTS TTFB         150–400 ms
  → playback net     20–80 ms
--------------------------------
E2E target p50 < 800 ms, p95 < 1800 ms
```

Optimizations: streaming everywhere, chunk TTS, connection reuse, skip retrieval when not needed, region colocated with LiveKit + providers, cache embeddings (**NEAR**), model routing (**LATER**).

**TTFT / TTFB / TTFA** defined in [glossary.md](glossary.md). Record all three on every turn.

---

## 13. Prompt compilation

From snapshot:

- system = join(personality, instructions, goals, constraints, guardrails)  
- tools schema (**NEAR**) from bound ToolVersions  
- knowledge: not dumped whole; retriever injects per turn (**NEAR**)  
- **Never** put provider API keys in the prompt  

LLM output is language + optional tool call JSON. Business facts come from tools.

---

## 14. Testing the runtime

| Test | How |
| --- | --- |
| Turn machine | Unit, fake clock, fake providers |
| Barge-in | Inject UserSpeechStarted during fake TTS; assert no further TTSChunk applied |
| Stale tokens | Send LLMToken after cancel; assert drop |
| Multi-turn | Three UserSpeechEnded events |
| Provider failure | Adapter raises; session not deadlocked |
| Network | Optional LiveKit local; else mock transport |

P1 must include the first five.

---

## 15. Observability

Spans: `session`, `turn`, `stt`, `llm`, `tts`, `interrupt`. Attributes: `session.id`, `agent.version_id`, `turn.id`, `provider.name` (adapter), usage tokens, `interrupted=true`.

Logs: JSON, `correlation_id=session_id`. **No raw audio, no secrets, no full prompt if org policy redacts (LATER); P1 may log prompt hashes + length.**

---

## 16. NOW / NEAR / LATER

| NOW | NEAR | LATER |
| --- | --- | --- |
| Loop, interrupt, STT, LLM, TTS | Tools, retrieve, inspector events persist | Workflows, memory, handoff, routing, resume |

---

## 17. Intentionally not in runtime

- HTTP CRUD for agents  
- React  
- Billing  
- Training models  
- Owning LiveKit SFU
