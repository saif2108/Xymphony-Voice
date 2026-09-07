# UI System

**Status:** Phase 0. **No frontend exists.** Design language: **Linear × Vercel × modern AI IDE × mission control** — dense, calm, high-contrast functional, not generic enterprise purple-gradient SaaS.

**Stack:** Next.js, React, TypeScript, Tailwind, shadcn/ui. Workflow editor: React Flow **LATER**.

Playground is a **dashboard route**, not a separate app ([architecture.md](architecture.md)).

Canonical terms: [glossary.md](glossary.md). Journey: [product-spec.md](product-spec.md).

---

## 1. Information architecture

```
/                       Landing
/sign-in  /sign-up
/[org]/                 Mission Control (Workspace home)
  agents/               List
  agents/new            Create
  agents/[id]/          Builder layout
    overview            Configuration
    voice               Voice studio
    knowledge           NEAR
    tools               NEAR
    workflow            LATER
    playground          Realtime test
    versions            LATER
  sessions/[id]         Inspector (NEAR; P1 mini in playground)
  evaluations           LATER
  simulations           LATER
  analytics             NEAR
  settings              Org, providers, members
```

---

## 2. Design tokens (intent)

- Background: near-black / zinc-950; surfaces zinc-900; borders subtle  
- Accent: one sharp accent (not rainbow)  
- Typography: geometric sans; tabular nums for latency  
- Motion: short (150ms); playground waveform is the only “alive” motion  
- Density: IDE-like in builder; marketing airy on landing only  

Empty / loading / error: skeleton for lists; inline error + retry; empty with **one** primary CTA.

Responsive: dashboard **desktop-first** (min 1024). Playground usable on tablet. Mobile: viewer **LATER**. P1 may be desktop-only.

---

## 3. Screens

For each: purpose, primary action, hierarchy, components, empty/loading/error, responsive, extensibility.

### 3.1 Landing

**Purpose:** explain platform. **Action:** Sign up / Sign in.  
**Hierarchy:** headline (“Build realtime AI agents”) → product loop → CTA.  
**Components:** nav, hero, feature grid (builder, playground, traces) — no fake metrics.  
**Empty/loading/error:** static.  
**Extensibility:** interactive demo **VISION**.

### 3.2 Sign-up / Sign-in

**Purpose:** create User + Organization. **Action:** submit.  
**Components:** email, password or IdP buttons.  
**Error:** invalid credentials, rate limit.  
**P1:** may be a single seeded user if IdP not chosen — still use these routes.

### 3.3 Workspace / Mission Control

**Purpose:** home. **Action:** create agent or resume last playground.  
**Hierarchy:** recent agents, recent sessions, system status (LiveKit/api) **NEAR**.  
**Empty:** “Create your first agent.”  
**Extensibility:** health scores TIER 2.

### 3.4 Agent list

**Purpose:** find agents. **Action:** open / create.  
**Components:** table/grid: name, updated, version status.  
**Empty:** CTA. **Loading:** skeleton. **Error:** retry.

### 3.5 Agent builder (shell)

**Purpose:** host sub-nav. **Action:** save draft (explicit).  
**Components:** left nav, header save/playground, dirty-state warning.  
**Extensibility:** tabs added without breaking P1 overview+voice+playground.

### 3.6 Agent configuration

**Purpose:** instructions, personality, LLM/STT select. **Action:** save.  
**Hierarchy:** identity → instructions → providers.  
**Components:** textarea, model selects from **adapter registry API**.  
**Error:** `provider_not_configured`.  
**P1 core screen.**

### 3.7 Voice studio

**Purpose:** TTS voice pick, optional sample playback **NEAR**. **Action:** select voice, save.  
**P1:** dropdown + preview if adapter supports.

### 3.8 Knowledge (NEAR)

Upload, status, bind to version. Empty: upload CTA. Error: ingest failed.

### 3.9 Tools (NEAR)

List tools, schema editor, bind. Empty: add REST/MCP.

### 3.10 Workflow builder (LATER)

React Flow canvas, node palette, publish. Empty: start template. Error: invalid graph.

### 3.11 Realtime playground (P1)

**Purpose:** talk. **Action:** connect, mute, barge-in naturally, disconnect.  
**Hierarchy:** connection status → waveform/agent state → transcript → session id.  
**Components:** Start, Mute, Stop; live captions; interrupt indicator.  
**Empty:** “Start session.” **Loading:** connecting to LiveKit. **Error:** mic denied, provider fail.  
**Extensibility:** split pane for Live Agent Brain **NEAR**.

### 3.12 Session inspector (NEAR)

Timeline of structured events. Primary: understand “why.” No CoT.  
**P1:** transcript list inside playground is enough.

### 3.13 Evaluation (LATER)

Datasets, run, scores.

### 3.14 Simulation lab (LATER)

Scenario picker, sim vs agent, scores.

### 3.15 Analytics (NEAR)

Charts from [observability.md](observability.md) product metrics.

### 3.16 Version history (NEAR)

List versions, publish, compare, rollback deployment **LATER**.

### 3.17 Settings

Provider credentials (write-only inputs), members **LATER**, retention.  
**P1:** paste LLM/STT/TTS keys into org secrets.

---

## 4. Live Agent Brain (NEAR)

Vertical timeline: User said → Transcript → Retrieve → Tool → Result → Response → TTS.  
Click node → payload JSON (redacted).

---

## 5. Accessibility

Playground: visible focus, captions as first-class (they are the product), do not rely on color for interrupt state (icon + text).

---

## 6. UI must not

- Contain business-policy engines  
- Call vendor SDKs except LiveKit client + mic  
- Embed provider secrets  
- Bypass control plane by writing localStorage as source of truth (cache only)
