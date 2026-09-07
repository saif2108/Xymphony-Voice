# ADR-008: LangGraph scope — internal workflow engine, not the product

- **Status:** Accepted  
- **Date:** 2026-09-07  

## Context

The platform needs visual workflows later. LangGraph is useful for durable graphs. Using it as the **voice runtime** would hide interruption and our Event model.

## Problem

When is LangGraph allowed?

## Decision

- **P1:** no LangGraph.  
- **Workflow executor (LATER):** may use LangGraph **inside** `packages/workflows` to step a **published WorkflowVersion**, mapping node types to our ports, emitting our events.  
- **Not allowed:** LangGraph as dashboard-facing model; LangGraph as LiveKit replacement; LLM-only graph with no ToolExecutor.

Public model remains nodes/edges in Postgres.

## Alternatives

| Alternative | Notes |
| --- | --- |
| Homegrown only | More control, more work — OK if LangGraph fights cancellation |
| Temporal | Different durability story; not P1 |

## Tradeoffs

- **+** Faster complex graphs later  
- **−** Two graph models if we leak LangGraph types — **forbidden in APIs**  

## Reconsider if

LangGraph cannot honor turn cancellation — then homegrown stepper.
