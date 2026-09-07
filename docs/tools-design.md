# Tools Design

**Status:** Phase 0. **Not in Prototype 1.** Horizon: **NEAR** (P2).  
**LLM is not the system of record.** Tools are.

---

## 1. Abstraction

A **Tool** is a named, schema-validated, permissioned, auditable function the **runtime** executes.

Kinds: REST, GraphQL, Python (sandboxed **LATER**), webhook, MCP, database (parameterized only), internal Xymphony service.

AgentVersion binds **ToolVersion IDs** (allowlist). The model cannot call an unbound tool.

---

## 2. ToolVersion fields

| Field | Purpose |
| --- | --- |
| name, description | LLM selection |
| input_schema / output_schema | JSON Schema |
| permissions | RBAC + data classes |
| auth_ref | pointer to provider_configs / secret |
| timeout_ms | default 10000 |
| retry_policy | only if `idempotent=true` |
| idempotency | key = `tool_call_id` |
| side_effect_class | `read` \| `write` |
| audit | write tools always audit |

---

## 3. Execution flow

```
LLMResponse.tool_calls
  → validate name ∈ allowlist
  → validate arguments vs schema
  → policy checks (escalation, amount caps as deterministic predicates)
  → ToolExecutor.run(cancel, timeout)
  → ToolResult event
  → LLM continues with result
```

**Bad:** model says “refund issued” without a tool.  
**Good:** `refund.execute` returns `{refunded: true, id}` then the model narrates.

---

## 4. Security

| Risk | Mechanism |
| --- | --- |
| SSRF | Allowlist hosts, block link-local, DNS rebinding checks, no file:// |
| Prompt injection → exfil | Tools that send outbound HTTP get destination allowlist; no “fetch any URL” tool by default |
| Tool poisoning (MCP) | Pin server hashes/versions; sandbox; review UI |
| Secrets in arguments | Redact logs; schema `writeOnly` |
| Confused deputy | Tenant credentials per org; no global Slack token |
| Python UDF | Not in P2 unless isolated process + no network; prefer HTTP |

See [security.md](security.md).

---

## 5. MCP (NEAR)

MCP servers are **adapters** producing ToolVersions. Same executor gate. Do not let MCP bypass allowlists.

---

## 6. Failure

Timeout → `ToolResult.ok=false`. Cancel → `cancelled`. Runtime may let LLM retry **read** tools; **write** tools require new `tool_call_id` and idempotency store.

---

## 7. Testing

Schema reject; SSRF suite; timeout; cancel; idempotent double-call.

---

## 8. Not in P1

No executor. Do not “quickly” add a hardcoded refund function in the runtime loop.
