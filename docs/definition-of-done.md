# Definition of Done

A change is not done because it “runs on my machine.”

---

## 1. General

- [ ] Implemented behind the correct abstraction (no vendor `if` in the runtime loop)  
- [ ] Typed (Pydantic / TypeScript)  
- [ ] Tested (automated at the cheapest honest level)  
- [ ] Integrated on `main` Compose path  
- [ ] Error handled (timeouts, 4xx/5xx mapped)  
- [ ] Logged (JSON, ids, no secrets)  
- [ ] Observable (span or metric if it is on the voice path)  
- [ ] Documented if architecture/contracts/UX flow changed  
- [ ] UI works (if user-facing) — exercise in browser, not screenshot-only  
- [ ] No regression of P1 playground once it exists  
- [ ] Git checkpoint (PR merged or explicit wip agreement)

---

## 2. Realtime extra

- [ ] Interruption tested  
- [ ] Cancellation tested (LLM + TTS)  
- [ ] Multiple turns tested  
- [ ] Provider failure tested  
- [ ] Network degradation considered (disconnect copy, retry)  
- [ ] Stale event handling tested  

---

## 3. Claiming completion to humans or AI agents

Do not claim a feature complete if only docs exist. Do not claim P1 complete if barge-in is untested.
