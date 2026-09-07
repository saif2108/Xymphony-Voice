# ADR-001: Use LiveKit for realtime media transport

- **Status:** Accepted  
- **Date:** 2026-09-07  
- **Deciders:** Phase 0 architecture  

## Context

Xymphony Voice is voice-first. Browsers need capture, jitter buffers, NAT traversal, A/V sync, and multi-participant rooms. Building an SFU/WebRTC stack is a company-sized product.

## Problem

How do we move audio between browser and Agent Runtime without making WebRTC our identity or calendar?

## Decision

Use **LiveKit** (self-hosted in Compose and/or LiveKit Cloud) as **MediaTransport** only.

- Rooms, tracks, tokens: LiveKit  
- Session, turn, interruption, providers: **Xymphony Agent Runtime**  
- Dashboard uses LiveKit client SDK for mic/speaker  
- Runtime worker joins as an agent participant  

We do **not** treat “LiveKit Agents framework defaults” as our architecture. If we use helpers, they wrap into our event loop, not replace it.

## Alternatives

| Alternative | Why not now |
| --- | --- |
| Raw `aiortc` / custom SFU | Undifferentiated, slow, security/ops burden |
| Daily, Agora, Twilio Programmable Voice as core | Similar: transport OK, but we still need a port; LiveKit OSS matches self-host VISION |
| WebSocket PCM only | Simpler demo, worse production (NAT, device handling, later video) |
| Speech-to-speech vendor data channel only | Bypasses STT/LLM/TTS ports; rejected for platform |

## Tradeoffs

- **+** Time-to-P1, mobile/telephony path later (LiveKit SIP **VISION**)  
- **−** Another moving part in Compose; version coupling  
- **−** Risk of accidentally coding “the LiveKit way” instead of our runtime  

## Consequences

- `packages/realtime` contains the LiveKit adapter  
- Tokens minted by control plane, not the browser with admin keys  
- Revisit transport without rewriting AgentVersion  

## Reconsider if

LiveKit cannot meet latency/SLA; license/ops conflict; a Channel needs a different media fabric — then add a second MediaTransport adapter, do not fork the runtime.
