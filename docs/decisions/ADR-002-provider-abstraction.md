# ADR-002: Provider abstraction (ports and adapters)

- **Status:** Accepted  
- **Date:** 2026-09-07  

## Context

The insurance POC pattern (one LLM, one STT, one TTS hardcoded) cannot be the platform. Vendors change price, quality, and region weekly.

## Problem

How does the runtime call models and speech services without becoming “the OpenAI app”?

## Decision

Define ports in `packages/contracts` / provider interfaces: `LLMProvider`, `STTProvider`, `TTSProvider`, `EmbeddingProvider`, `VectorStore`, `ToolExecutor`, `KnowledgeRetriever`, `MediaTransport`.

Adapters live in `packages/providers`. Runtime imports ports only.

AgentVersion stores `{provider_key, model, params}` not SDK objects. Secrets in `provider_configs`.

Capability flags gate binds (no tools on a model that cannot call them).

P1: **one live adapter per port is enough**, plus fakes for tests. A second adapter may be a stub.

## Alternatives

| Alternative | Why not |
| --- | --- |
| Direct SDK in loop | Rewrite runtime per vendor; kills routing |
| LangChain as the runtime | Hides our interruption/session product; OK as optional helper inside an adapter, not the architecture |
| Lowest-common-denominator only, no flags | Forces us to fake tool calling poorly |

## Tradeoffs

- **+** Replaceability, testability, future routing  
- **−** Slightly more P1 code than `import openai` in the worker  
- **−** Wrapper bugs  

## Consequences

CLAUDE.md forbids bypassing ports. Contract tests per adapter.

## Reconsider if

A single foundation-model vendor offers an end-to-end voice API we must use — still wrap it as **one** adapter that may internally multiplex, without leaking into session state machine.
