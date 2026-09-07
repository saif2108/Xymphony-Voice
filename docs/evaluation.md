# Evaluation and Simulation

**Status:** Phase 0. **Not P1.** Horizon: **LATER** (Beta) for eval; simulation lab alongside or just after.

Agents are not “up” because HTTP 200.

---

## 1. Objects

```
EvaluationDataset → Scenario (inputs, constraints, expected outcomes)
  → Execution (against AgentVersion)
  → Trace (session events)
  → Score[] from Evaluator
  → Metric aggregates
```

**Evaluators:** deterministic (regex, tool-arg equality, JSON path), LLM-as-judge (via LLM port + rubric schema), human.

---

## 2. Dimensions

Task success, response quality, tool correctness, policy adherence, hallucination (grounding vs retrieval), retrieval quality, latency, cost, interruption handling, workflow correctness, escalation correctness.

---

## 3. Regression

CI **LATER**: curated dataset, fail PR if `task_success` drops > threshold (**TBD**) on pinned AgentVersion fixtures with **fake tools**.

---

## 4. Simulation lab

AI **user simulator** is a separate AgentVersion with goals like “interrupt”, “be ambiguous”, “solicit policy violation.”

```
Simulator Session ↔ Target Agent Session
  (same event model; channel=simulation)
→ scores
```

Must not use production write tools; bind **sandbox tool adapters**.

---

## 5. “Optimize agent” (LATER)

Reads eval + observability; proposes new draft AgentVersion (model, routing, context). Human apply.

---

## 6. Why design now

Traces (`turn_id`, tools, retrieval) must be **stable** so later judges can consume them. P1 event envelope is the eval API.
