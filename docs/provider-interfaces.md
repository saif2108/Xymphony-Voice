# Provider Interfaces (Ports)

**Status:** Phase 0. Runtime depends on these ports; adapters implement them.  
**Decision:** [ADR-002](decisions/ADR-002-provider-abstraction.md)  
**Rule:** Do not import vendor SDKs in `agent-runtime`.

Capability flags are **declared**, not assumed.

---

## 1. Common types

```
ProviderError { code, message, retryable, http_status?, cause? }

Usage { input_units, output_units, unit: tokens|characters|seconds|bytes, estimated_cost_usd? }

Latency { start, first_byte_at?, end }

CancelToken  # cooperative; adapters must check between chunks

Capability {
  streaming: bool
  cancellation: bool
  tool_calling: bool
  structured_output: bool
  vision: bool
  audio_in: bool
  audio_out: bool
}
```

Every call returns or streams `metadata: { provider, model, request_id, usage, latency }`.

**Errors:** Timeouts raise `ProviderError(code=timeout, retryable=true)` unless the turn is cancelled (`code=cancelled, retryable=false`).

**Health:** `async health() -> {ok, lag_ms?}` for **LATER** routing.

---

## 2. LLMProvider

**Inputs:** `messages: ContentPart[]`, `system`, `tools[]?`, `params` (temperature, max_tokens), `cancel`, `response_format?`.

**Outputs:** stream of `LLMToken` then `LLMResponse` with `finish_reason`, optional `tool_calls`.

**Streaming:** required for P1 voice.

**Cancellation:** required for barge-in.

**Capability negotiation:** If AgentVersion requires tools and adapter `tool_calling=false`, control plane **rejects** bind at save time; runtime fails closed if snapshot is inconsistent.

**Replace:** new class `AnthropicLLMAdapter(LLMProvider)`.

**P1 adapters:** at least one of OpenAI-compatible, Anthropic, Gemini, Ollama — **one live**, others optional stubs.

**Not:** the LLM adapter must not execute tools.

---

## 3. STTProvider

**Inputs:** audio stream (PCM/Opus as specified by adapter), language hint, `cancel`.

**Outputs:** stream `TranscriptFrame` (`is_final` true/false).

**Streaming:** required P1.

**Errors:** connection drop → retry policy in runtime.

**Capabilities:** `interim_results`, `word_timestamps`, `language_detect`.

**Replace:** AssemblyAI / Whisper / Deepgram adapters.

---

## 4. TTSProvider

**Inputs:** text chunk, `voice_id`, `speed?`, `cancel`.

**Outputs:** audio byte stream (runtime converts to LiveKit frames).

**Streaming:** required P1 (first byte before full utterance).

**Cancellation:** required.

**Capabilities:** `ssml`, `timestamps`, `streaming`.

**Replace:** ElevenLabs / Cartesia / Piper.

---

## 5. EmbeddingProvider (NEAR)

**Inputs:** `{texts[], model}`. **Outputs:** `{vectors[][], usage}`. Batch ingest + query-time query embedding.

---

## 6. VectorStore (NEAR)

**Inputs:** upsert chunks `{id, organization_id, project_id, source_id, vector, metadata}`; query `{vector, k, filters}`.

**Outputs:** `{id, score, metadata}[]`.

**Filters must include organization_id + project_id.** Missing filter is a bug.

**Replace:** pgvector now ([ADR-003](decisions/ADR-003-postgres-pgvector.md)); later Pinecone/Weaviate behind same port.

---

## 7. KnowledgeRetriever (NEAR)

**Inputs:** `{query, agent_version snapshot bindings, turn_id, cancel}`.  
**Outputs:** `RetrievalResult` (chunks, scores, citation ids).  
**May:** rerank. **Must not:** call LLM as the store.

---

## 8. ToolExecutor (NEAR)

**Inputs:** `{tool_version, arguments, timeout, cancel, idempotency_key}`.  
**Outputs:** `{ok, data, error}` JSON-serializable.  
**Must:** enforce allowlist, SSRF policy, redaction. See [tools-design.md](tools-design.md).

---

## 9. MediaTransport

**Inputs:** join `{room, token}`, callbacks for audio frames.  
**Outputs:** publish audio, participant events.  
**NOW adapter:** LiveKit ([ADR-001](decisions/ADR-001-use-livekit.md)).

---

## 10. Model routing (LATER)

Policy engine **outside** adapters:

```
route(snapshot, turn_context) -> {provider, model}
  considering: capability, cost_limit, latency_class, data_residency, health
fallback: ordered list on ProviderError.retryable
sensitive ops: approved_models only (guardrail)
```

P1: `route` = identity function on snapshot bindings.

---

## 11. Testing adapters

Contract tests (fake server or recorded): stream, cancel mid-stream, timeout, usage populated. Runtime tests use `FakeLLM` / `FakeSTT` / `FakeTTS` only.

---

## 12. What we will not do

- Branch `if provider == "openai"` in the loop  
- Encode ElevenLabs as the only voice object in AgentVersion (store `provider_key` + `voice_ref`)  
- Ship 20 adapters in P1
