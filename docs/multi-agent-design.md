# Multi-Agent Design

**Status:** Phase 0. **LATER / VISION.** P1 is single AgentVersion per Session.

---

## 1. Pattern

```
Supervisor Agent  →  Specialist Agents  →  Tools
```

Example: Customer → Billing | Technical | Escalation.

---

## 2. Handoff

Event `AgentTransferred` `{from_agent_id, to_agent_id, reason, summary_ref}`.

**Session ownership:** one Session remains; `active_agent_version_id` changes; history preserved.

**Shared context:** transcript + structured state + **summary** (token-bounded). Do not dump another agent’s hidden CoT (we do not store it).

**Permissions:** target agent’s tool allowlist applies after handoff. Supervisor cannot grant extra tools via prompt.

**Trace:** same `trace_id`; span `handoff`.

**Failure:** target unavailable → Error + stay on supervisor or escalate to human.

---

## 3. vs workflows

Workflow Agent Handoff **node** is the deterministic version. Supervisor LLM routing is the flexible version. Both emit the same event.

---

## 4. Not P1

No multi-agent bus, no A2A protocol. Do not spawn child LiveKit rooms per specialist in P1.

---

## 5. Human-in-the-loop (LATER)

Not a separate product: humans are **another participant** on the same Session.

| Mode | Behavior |
| --- | --- |
| **Escalation** | Workflow/guardrail emits `HumanTakeover` request; session waits; UI Mission Control queues |
| **Takeover** | Operator (org member) joins; TTS from agent **stops**; operator audio/text is the output path; runtime `source=human` |
| **Approval** | Write tools with `requires_approval` pause before HTTP; operator confirms; then execute |
| **Review** | Async: transcript + trace sent to reviewer; not live |

**Inheritance on takeover:** full transcript Messages, short-term summary if any, committed tool results, retrieval citations, user identity metadata, workflow node id. **Not:** hidden CoT (we do not store it).

**Permissions:** operator RBAC; tools during human mode may be disabled or operator-triggered only (AgentVersion policy).

**Failure:** no operator within `escalation_timeout_sec` (**TBD**, proposed 60s) → configured fallback message + session continue or terminate.
