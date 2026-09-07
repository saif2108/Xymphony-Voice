# Workflow Design

**Status:** Phase 0. **Not P1.** Editor **LATER** (React Flow). Executor **LATER** (may use LangGraph internally: [ADR-008](decisions/ADR-008-langgraph-scope.md)).

**A Workflow is not an Agent.** An AgentVersion **may** point at a WorkflowVersion.

---

## 1. Why workflows exist

Freeform ReAct is insufficient when legal/ops require **deterministic paths** (e.g. verify identity → lookup → refund cap → escalate). Workflows constrain the runtime.

---

## 2. Graph model

```
WorkflowVersion.graph = {
  nodes: [{ id, type, config }],
  edges: [{ from, to, condition? }]
}
```

**Node types (conceptual):** Start, End, LLM, Condition, Tool, Knowledge Retrieval, Human Handoff, Agent Handoff, Wait, Transform, Parallel, Merge, Webhook, Sub-agent.

**State:** workflow-scoped JSON (inputs, node outputs). Persisted per session when executor exists (`workflow_runs` **LATER**).

**Transitions:** edge conditions as JSONLogic or CEL-like expressions over state — **not** unconstrained LLM “pick any node” unless node type is LLM router with an allowlist of next ids.

---

## 3. Runtime relationship

```
Turn starts
  → if snapshot.workflow_version_id is null: default LLM loop
  → else: WorkflowExecutor.step() until wait/LLM/end
       → same ToolExecutor, Retriever, LLM ports
       → WorkflowTransition events
```

Retries: node-level, idempotent tools only. Errors: edge to error handler or End(failed).

---

## 4. Versioning

Publish freezes graph. Running sessions keep old WorkflowVersion. Editor drafts do not affect prod.

---

## 5. Traces

Each node = OTel span + `WorkflowTransition`. Live Agent Brain shows node ids, not CoT.

---

## 6. Frontend

React Flow in dashboard. Contracts: graph JSON schema in `packages/contracts`. Backend validates cycles, single Start, reachable End.

---

## 7. P1

`workflow_version_id` nullable in the conceptual AgentVersion. No executor, no editor. Do not implement a fake graph.
