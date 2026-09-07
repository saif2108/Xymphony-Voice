# Engineer A / Saif — status

**Role:** Data plane — runtime, events, session loop, providers, interruption, voice pipeline.  
**See:** [work-allocation.md](../work-allocation.md)

## Current (Phase 0)

- No runtime code in repo.  
- Design to implement next: [runtime-design.md](../runtime-design.md), [event-model.md](../event-model.md), [prototype-1.md](../prototype-1.md).

## Next (Phase 1)

- `packages/contracts` event + snapshot types  
- `packages/agent-runtime` SessionController + fakes  
- LiveKit worker join  
- Real STT/LLM/TTS adapters + barge-in tests  

## Blockers

- Phase 1 not started (intentional).  
- Vendor keys for first live adapters (unresolved which vendors are enabled day one).
