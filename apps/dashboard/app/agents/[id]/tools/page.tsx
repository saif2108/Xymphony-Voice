"use client";

import { useState } from "react";
import { Wrench, Plus, Check, Code, ExternalLink, ShieldCheck } from "lucide-react";

interface ToolItem {
  id: string;
  name: string;
  description: string;
  category: "builtin" | "custom" | "integration";
  enabled: boolean;
  parameters: {
    type: string;
    properties: Record<string, { type: string; description: string }>;
  };
}

const DEFAULT_TOOLS: ToolItem[] = [
  {
    id: "end_call",
    name: "end_call",
    description: "Gracefully disconnects the phone or audio session when the conversation is finished.",
    category: "builtin",
    enabled: true,
    parameters: {
      type: "object",
      properties: {
        reason: { type: "string", description: "Reason why the call is ending." },
      },
    },
  },
  {
    id: "transfer_call",
    name: "transfer_call",
    description: "Transfers the caller to a human agent or external phone department.",
    category: "builtin",
    enabled: false,
    parameters: {
      type: "object",
      properties: {
        department: { type: "string", description: "Target department or extension." },
        summary: { type: "string", description: "Summary of user request for handoff." },
      },
    },
  },
  {
    id: "webhook_dispatch",
    name: "webhook_dispatch",
    description: "Triggers an external HTTPS webhook to record booking, CRM update, or action.",
    category: "integration",
    enabled: true,
    parameters: {
      type: "object",
      properties: {
        action: { type: "string", description: "The action name to dispatch." },
        payload: { type: "string", description: "JSON string payload to send." },
      },
    },
  },
];

export default function ToolsPage() {
  const [tools, setTools] = useState<ToolItem[]>(DEFAULT_TOOLS);
  const [isCreating, setIsCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [newParams, setNewParams] = useState("{\n  \"query\": {\n    \"type\": \"string\",\n    \"description\": \"Search query\"\n  }\n}");
  const [error, setError] = useState("");

  function toggleTool(id: string) {
    setTools((prev) =>
      prev.map((tool) =>
        tool.id === id ? { ...tool, enabled: !tool.enabled } : tool
      )
    );
  }

  function handleCreateTool(e: React.FormEvent) {
    e.preventDefault();
    if (!newName.trim()) {
      setError("Tool name is required");
      return;
    }

    try {
      const parsed = JSON.parse(newParams);
      const newTool: ToolItem = {
        id: newName.toLowerCase().replace(/[^a-z0-9_]/g, "_"),
        name: newName.trim(),
        description: newDescription.trim(),
        category: "custom",
        enabled: true,
        parameters: {
          type: "object",
          properties: parsed,
        },
      };

      setTools((prev) => [...prev, newTool]);
      setIsCreating(false);
      setNewName("");
      setNewDescription("");
      setError("");
    } catch {
      setError("Parameters must be valid JSON object representing properties");
    }
  }

  return (
    <div className="mx-auto max-w-[1100px] px-8 py-10">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-[0.12em] text-neutral-400">
            Agent capabilities
          </p>
          <h2 className="mt-2 text-[22px] font-semibold tracking-[-0.03em]">
            Tools & Actions
          </h2>
          <p className="mt-1 text-[13px] text-neutral-500">
            Equip your agent with function calling tools to query databases, call APIs, or execute actions during calls.
          </p>
        </div>

        <button
          onClick={() => setIsCreating(!isCreating)}
          className="flex h-9 items-center gap-1.5 rounded-lg bg-neutral-950 px-3.5 text-[12px] font-medium text-white transition-colors hover:bg-neutral-800"
        >
          <Plus className="h-3.5 w-3.5" />
          Add custom tool
        </button>
      </div>

      {isCreating && (
        <form
          onSubmit={handleCreateTool}
          className="mb-6 rounded-xl border border-neutral-300 bg-white p-6 shadow-sm"
        >
          <h3 className="text-[14px] font-semibold text-neutral-900">
            Create Custom Tool
          </h3>
          <p className="mt-1 text-[12px] text-neutral-500">
            Define a tool definition with JSON Schema parameters for the LLM.
          </p>

          {error && (
            <div className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-700">
              {error}
            </div>
          )}

          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <div>
              <label className="mb-1.5 block text-[12px] font-medium text-neutral-700">
                Tool Function Name
              </label>
              <input
                type="text"
                placeholder="e.g. check_order_status"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                className="h-10 w-full rounded-lg border border-neutral-300 bg-white px-3 font-mono text-[12px] outline-none focus:border-neutral-500 focus:ring-2 focus:ring-neutral-100"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-[12px] font-medium text-neutral-700">
                Description for LLM
              </label>
              <input
                type="text"
                placeholder="Explains when the LLM should invoke this tool"
                value={newDescription}
                onChange={(e) => setNewDescription(e.target.value)}
                className="h-10 w-full rounded-lg border border-neutral-300 bg-white px-3 text-[12px] outline-none focus:border-neutral-500 focus:ring-2 focus:ring-neutral-100"
              />
            </div>
          </div>

          <div className="mt-4">
            <label className="mb-1.5 block text-[12px] font-medium text-neutral-700">
              Parameters Schema (Properties object)
            </label>
            <textarea
              rows={4}
              value={newParams}
              onChange={(e) => setNewParams(e.target.value)}
              className="w-full rounded-lg border border-neutral-300 bg-neutral-50/50 p-3 font-mono text-[12px] outline-none focus:border-neutral-500 focus:ring-2 focus:ring-neutral-100"
            />
          </div>

          <div className="mt-4 flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={() => setIsCreating(false)}
              className="h-8 rounded-lg px-3 text-[12px] text-neutral-500 hover:bg-neutral-100"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="flex h-8 items-center gap-1.5 rounded-lg bg-neutral-950 px-3 text-[12px] font-medium text-white hover:bg-neutral-800"
            >
              Save Tool
            </button>
          </div>
        </form>
      )}

      {/* Tools List */}
      <div className="space-y-3">
        {tools.map((tool) => (
          <div
            key={tool.id}
            className="rounded-xl border border-neutral-200 bg-white p-5 transition-shadow hover:shadow-sm"
          >
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-start gap-3.5">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-neutral-200 bg-neutral-50 text-neutral-600">
                  <Wrench className="h-4 w-4" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-[13px] font-semibold text-neutral-900">
                      {tool.name}
                    </span>
                    <span
                      className={`rounded px-1.5 py-0.5 text-[10px] font-medium capitalize ${
                        tool.category === "builtin"
                          ? "bg-neutral-100 text-neutral-600"
                          : "bg-blue-50 text-blue-700 border border-blue-200"
                      }`}
                    >
                      {tool.category}
                    </span>
                  </div>
                  <p className="mt-1 text-[12px] text-neutral-500 leading-relaxed">
                    {tool.description}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-3 shrink-0">
                <button
                  type="button"
                  onClick={() => toggleTool(tool.id)}
                  className={`flex h-8 items-center gap-1.5 rounded-lg px-3 text-[11px] font-medium transition-colors ${
                    tool.enabled
                      ? "border border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100"
                      : "border border-neutral-200 bg-neutral-50 text-neutral-500 hover:bg-neutral-100"
                  }`}
                >
                  {tool.enabled ? (
                    <>
                      <Check className="h-3 w-3" />
                      Enabled
                    </>
                  ) : (
                    "Disabled"
                  )}
                </button>
              </div>
            </div>

            {/* Parameter preview */}
            <div className="mt-3.5 rounded-lg border border-neutral-100 bg-neutral-50 px-3 py-2">
              <div className="flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-wider text-neutral-400">
                <Code className="h-3 w-3" />
                Parameters
              </div>
              <div className="mt-1 flex flex-wrap gap-2 text-[11px] font-mono text-neutral-600">
                {Object.keys(tool.parameters.properties).length > 0 ? (
                  Object.entries(tool.parameters.properties).map(([key, val]) => (
                    <span
                      key={key}
                      className="rounded bg-white border border-neutral-200 px-1.5 py-0.5"
                    >
                      {key}: <span className="text-neutral-400">{val.type}</span>
                    </span>
                  ))
                ) : (
                  <span className="text-neutral-400">No arguments required</span>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-8 rounded-xl border border-neutral-200 bg-neutral-50/60 p-5">
        <div className="flex items-center gap-2 text-[12px] font-semibold text-neutral-800">
          <ShieldCheck className="h-4 w-4 text-emerald-600" />
          Deterministic Tool Execution Boundary
        </div>
        <p className="mt-1 text-[12px] text-neutral-500 leading-relaxed">
          Tools execute within the Xymphony agent runtime domain registry with validation, timeout guardrails, and error handling. Tool execution results are returned directly to the active LLM context without latency leaks.
        </p>
      </div>
    </div>
  );
}
