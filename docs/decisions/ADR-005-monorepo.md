# ADR-005: Monorepo

- **Status:** Accepted  
- **Date:** 2026-09-07  

## Context

Two engineers, shared Event/AgentVersion contracts, dashboard + API + worker. Polyrepo would freeze us on version ping-pong.

## Problem

How to organize code so contracts stay compatible and PRs stay reviewable?

## Decision

**One git repository** (`Xymphony-Voice`) with `apps/*` and `packages/*` created **when they gain code**. Python: `uv` or poetry workspace / hatch — Phase 1 picks one. JS: dashboard in `apps/dashboard`.

No empty package explosion in Phase 0.

## Alternatives

| Alternative | Why not |
| --- | --- |
| Repos per package | Contract drift |
| Only a Next.js app with API routes | Hides Python runtime; worse AI/ML ecosystem |
| Micro-repos + git submodules | Pain |

## Tradeoffs

- **+** Atomic PRs across API + runtime  
- **−** CI complexity grows — start simple  
- **−** Language mix in one repo — accepted  

## Consequences

`main` is the integration branch. CLAUDE.md: do not add packages without modules+tests.

## Reconsider if

A truly independent SDK with a separate release cadence — then extract `packages/contracts` publish, not before V1 need.
