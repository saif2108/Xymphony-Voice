
"use client";

import Link from "next/link";
import { Plus, Search, Sparkles } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import DashboardShell from "../components/dashboard-shell";

const API_URL = "http://localhost:8000";
const PROJECT_ID = "00000000-0000-4000-8000-000000000002";

type Agent = {
  id: string;
  name: string;
  description?: string | null;
  status?: string | null;
  tags?: string[];
  created_at?: string;
  updated_at?: string;
};

type AgentsResponse = {
  items: Agent[];
  next_cursor?: string | null;
};

function formatDate(value?: string) {
  if (!value) return "—";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "—";
  }

  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(date);
}

export default function AgentsPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadAgents() {
      try {
        setLoading(true);
        setError(null);

        const response = await fetch(
          `${API_URL}/v1/projects/${PROJECT_ID}/agents`
        );

        if (!response.ok) {
          throw new Error(`Failed to load agents (${response.status})`);
        }

        const data: AgentsResponse = await response.json();

        setAgents(data.items ?? []);
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Failed to load agents."
        );
      } finally {
        setLoading(false);
      }
    }

    loadAgents();
  }, []);

  const filteredAgents = useMemo(() => {
    const query = search.trim().toLowerCase();

    if (!query) {
      return agents;
    }

    return agents.filter((agent) => {
      return (
        agent.name.toLowerCase().includes(query) ||
        agent.description?.toLowerCase().includes(query)
      );
    });
  }, [agents, search]);

  return (
    <DashboardShell breadcrumb="Agents">
      <div className="mx-auto max-w-[1080px] px-8 py-12">
        <div className="flex items-end justify-between border-b border-neutral-200 pb-7">
          <div>
            <p className="text-[11px] font-medium uppercase tracking-[0.1em] text-neutral-400">
              Workspace
            </p>

            <h1 className="mt-2 text-[28px] font-semibold tracking-[-0.035em]">
              Agents
            </h1>

            <p className="mt-2 text-[13px] text-neutral-500">
              Create and configure your realtime AI agents.
            </p>
          </div>

          <Link
            href="/agents/new"
            className="flex h-8 items-center gap-1.5 rounded-md border border-neutral-200 px-3 text-[11px] font-medium text-neutral-700 transition-colors hover:bg-neutral-50"
          >
            <Plus className="h-3.5 w-3.5" />
            Create agent
          </Link>
        </div>

        <div className="mt-6 flex h-9 items-center gap-2 border-b border-neutral-200 pb-2">
          <Search className="h-3.5 w-3.5 text-neutral-400" />

          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search agents..."
            className="w-full bg-transparent text-[12px] outline-none placeholder:text-neutral-400"
          />
        </div>

        <section className="mt-4">
          {loading && (
            <div className="border-b border-neutral-200 py-10 text-center text-[12px] text-neutral-400">
              Loading agents...
            </div>
          )}

          {error && !loading && (
            <div className="border-b border-neutral-200 py-10 text-center">
              <p className="text-[12px] font-medium text-neutral-700">
                Could not load agents
              </p>

              <p className="mt-1 text-[11px] text-neutral-400">
                {error}
              </p>
            </div>
          )}

          {!loading && !error && agents.length === 0 && (
            <div className="border-b border-neutral-200 py-14 text-center">
              <div className="mx-auto flex h-9 w-9 items-center justify-center rounded-md border border-neutral-200">
                <Sparkles
                  className="h-4 w-4 text-neutral-500"
                  strokeWidth={1.7}
                />
              </div>

              <p className="mt-4 text-[12px] font-medium">
                No agents yet
              </p>

              <p className="mt-1 text-[11px] text-neutral-400">
                Create your first agent to get started.
              </p>

              <Link
                href="/agents/new"
                className="mt-5 inline-flex h-8 items-center gap-1.5 rounded-md bg-neutral-950 px-3 text-[11px] font-medium text-white"
              >
                <Plus className="h-3.5 w-3.5" />
                Create agent
              </Link>
            </div>
          )}

          {!loading &&
            !error &&
            agents.length > 0 &&
            filteredAgents.length === 0 && (
              <div className="border-b border-neutral-200 py-10 text-center text-[12px] text-neutral-400">
                No agents match your search.
              </div>
            )}

          {!loading &&
            !error &&
            filteredAgents.map((agent) => (
              <Link
                key={agent.id}
                href={`/agents/${agent.id}/overview`}
                className="group flex items-center justify-between border-b border-neutral-200 py-5 transition-colors hover:bg-neutral-50"
              >
                <div className="flex min-w-0 items-center gap-4">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-neutral-200">
                    <Sparkles
                      className="h-4 w-4 text-neutral-600"
                      strokeWidth={1.7}
                    />
                  </div>

                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="truncate text-[12px] font-medium">
                        {agent.name}
                      </p>

                      {agent.status && (
                        <span className="rounded-full border border-neutral-200 px-2 py-0.5 text-[9px] text-neutral-500">
                          {agent.status}
                        </span>
                      )}
                    </div>

                    <p className="mt-1 truncate text-[11px] text-neutral-400">
                      {agent.description || "No description"}
                    </p>
                  </div>
                </div>

                <div className="ml-4 flex shrink-0 items-center gap-6">
                  <span className="hidden text-[10px] text-neutral-400 sm:block">
                    Updated {formatDate(agent.updated_at)}
                  </span>

                  <span className="text-[12px] text-neutral-300 transition-colors group-hover:text-neutral-700">
                    →
                  </span>
                </div>
              </Link>
            ))}
        </section>
      </div>
    </DashboardShell>
  );
}

