# Work Allocation, Git, and Team

**Team:** two engineers. Not silos — contracts and playground are shared.

---

## 1. Engineer A / Saif — data plane

Owns: realtime runtime, event/frame architecture, session management, agent loop, LLM integration via ports, tool execution (**NEAR**), state, interruption/cancellation, streaming, provider abstraction, voice pipeline, orchestration, backend evaluation (**LATER**), memory (**LATER**), multi-agent runtime (**LATER**).

Primary trees (when they exist): `packages/agent-runtime`, `packages/realtime`, `packages/providers`, `apps/runtime-worker`, `tests/realtime`.

---

## 2. Engineer B / Partner — control plane + UI

Owns: dashboard, control-plane API, auth/RBAC, database models/migrations, agent CRUD/configuration, knowledge UI (**NEAR**), workflow editor (**LATER**), playground **UI**, session inspector UI, frontend analytics.

Primary trees: `apps/dashboard`, `apps/api`, `tests/e2e`.

---

## 3. Shared (no orphan zones)

| Area | How |
| --- | --- |
| `packages/contracts` | Pair on PRs; both can merge with review |
| RAG | Partner: upload UI + jobs API; Saif: retriever in loop |
| Observability | Shared span names from [observability.md](observability.md) |
| Testing | Both write; realtime tests Saif; Playwright partner |
| Playground | UI partner; session protocol Saif; integrate daily |

---

## 4. PR expectations

- Small PRs (< ~400 lines when possible)  
- Must not break `main` playground slice once it exists  
- Include tests for behavior changes  
- Update docs if architecture or contracts change  
- No secrets  
- Conventional commits: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`  

Review: the other engineer reviews cross-boundary PRs (contracts, session API, event types).

---

## 5. Git strategy

```
main              # always releasable toward current prototype
saif/realtime-*   # short-lived
partner/dashboard-*
feat/<topic>
```

- **No weeks-long branches.** Integrate via `main` every 1–2 days.  
- Merge: **squash or merge commits** — prefer squash for feature branches; no `--force` on `main`.  
- **Checkpoints:** tags `proto-1`, etc. ([roadmap.md](roadmap.md))  
- **Release tags:** only when we ship a named prototype.  
- **Docs:** same PR as code for contract changes.

P1 branch naming is a suggestion, not a permission to diverge.

---

## 6. Status files

Update weekly:

- [status/saif.md](status/saif.md)  
- [status/partner.md](status/partner.md)  

---

## 7. Parallelization audit (Phase 0)

**Can they work in parallel?** Yes, after M0 Compose + contracts:

- Partner: agent CRUD UI/API, settings secrets, playground chrome  
- Saif: SessionController + fakes + LiveKit worker  

**Blockers to avoid:** changing Event envelope without telling UI; minting LiveKit tokens in the worker instead of API; storing config only in Redis.

---

## 8. Communication

Written: ADRs + status files.  
Unblock: snapshot JSON shape is the daily interface.
