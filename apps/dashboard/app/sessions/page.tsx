"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { MessageSquare, PhoneCall, Clock, Sparkles, ArrowRight, Search, Play } from "lucide-react";
import DashboardShell from "../components/dashboard-shell";

const API_BASE_URL = "http://localhost:8000";
const PROJECT_ID = "00000000-0000-4000-8000-000000000002";

interface SessionInfo {
  id: string;
  agent_id: string;
  agent_version_id?: string;
  channel: string;
  status: string;
  created_at: string;
}

export default function SessionsPage() {
  const [sessionInput, setSessionInput] = useState("");
  const [selectedSession, setSelectedSession] = useState<SessionInfo | null>(null);
  const [messages, setMessages] = useState<Array<{ id: string; role: string; content: string }>>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleLookup(idToLookup?: string) {
    const targetId = (idToLookup || sessionInput).trim();
    if (!targetId) return;

    setLoading(true);
    setError("");
    setSelectedSession(null);
    setMessages([]);

    try {
      const [sessRes, msgRes] = await Promise.all([
        fetch(`${API_BASE_URL}/v1/projects/${PROJECT_ID}/sessions/${targetId}`),
        fetch(`${API_BASE_URL}/v1/projects/${PROJECT_ID}/sessions/${targetId}/messages`),
      ]);

      if (!sessRes.ok) {
        throw new Error(`Session not found (${sessRes.status})`);
      }

      const sessData: SessionInfo = await sessRes.json();
      setSelectedSession(sessData);

      if (msgRes.ok) {
        const msgData = await msgRes.json();
        setMessages(msgData.items ?? []);
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to load session");
    } finally {
      setLoading(false);
    }
  }

  return (
    <DashboardShell showCreateAgent={false}>
      <div className="mx-auto max-w-[1100px] px-8 py-10">
        <div className="mb-8 flex items-center justify-between">
          <div>
            <h1 className="text-[26px] font-semibold tracking-[-0.04em]">
              Sessions
            </h1>
            <p className="mt-1 text-[13px] text-neutral-500">
              Inspect live audio sessions, caller transcripts, and agent turns.
            </p>
          </div>

          <Link
            href="/agents"
            className="flex h-9 items-center gap-1.5 rounded-lg bg-neutral-950 px-3.5 text-[12px] font-medium text-white transition-colors hover:bg-neutral-800"
          >
            <Play className="h-3.5 w-3.5 fill-current" />
            Launch Playground
          </Link>
        </div>

        {/* Lookup session bar */}
        <div className="mb-6 rounded-xl border border-neutral-200 bg-white p-5">
          <label className="mb-2 block text-[12px] font-medium text-neutral-700">
            Lookup Session by ID
          </label>
          <div className="flex gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-2.5 h-4 w-4 text-neutral-400" />
              <input
                type="text"
                placeholder="Enter session UUID (e.g. from playground or worker)..."
                value={sessionInput}
                onChange={(e) => setSessionInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleLookup()}
                className="h-10 w-full rounded-lg border border-neutral-300 bg-white pl-9 pr-3 text-[13px] font-mono outline-none focus:border-neutral-500 focus:ring-2 focus:ring-neutral-100"
              />
            </div>
            <button
              onClick={() => handleLookup()}
              disabled={loading || !sessionInput.trim()}
              className="flex h-10 items-center gap-1.5 rounded-lg bg-neutral-950 px-4 text-[12px] font-medium text-white transition-colors hover:bg-neutral-800 disabled:bg-neutral-200"
            >
              {loading ? "Searching..." : "Inspect"}
            </button>
          </div>

          {error && (
            <p className="mt-3 text-[12px] text-red-600">{error}</p>
          )}
        </div>

        {selectedSession ? (
          <div className="space-y-6">
            <div className="rounded-xl border border-neutral-200 bg-white p-6">
              <div className="flex items-center justify-between border-b border-neutral-100 pb-4">
                <div>
                  <span className="font-mono text-[11px] uppercase tracking-wider text-neutral-400">
                    Session details
                  </span>
                  <h3 className="mt-1 font-mono text-[15px] font-semibold text-neutral-900">
                    {selectedSession.id}
                  </h3>
                </div>
                <span className="rounded-full border border-neutral-200 bg-neutral-50 px-3 py-1 text-[11px] font-medium text-neutral-700 capitalize">
                  {selectedSession.status}
                </span>
              </div>

              <div className="mt-4 grid grid-cols-2 gap-4 text-[12px] sm:grid-cols-4">
                <div>
                  <span className="text-neutral-400">Channel</span>
                  <p className="font-medium text-neutral-800 capitalize">
                    {selectedSession.channel}
                  </p>
                </div>
                <div>
                  <span className="text-neutral-400">Agent ID</span>
                  <p className="font-mono text-[11px] text-neutral-800 truncate">
                    {selectedSession.agent_id}
                  </p>
                </div>
                <div>
                  <span className="text-neutral-400">Created At</span>
                  <p className="font-medium text-neutral-800">
                    {new Date(selectedSession.created_at).toLocaleString()}
                  </p>
                </div>
              </div>
            </div>

            {/* Transcript Messages */}
            <div className="rounded-xl border border-neutral-200 bg-white p-6">
              <h4 className="text-[13px] font-semibold text-neutral-900">
                Turn Transcript
              </h4>

              {messages.length === 0 ? (
                <p className="mt-4 text-[12px] text-neutral-500">
                  No turn messages recorded for this session yet.
                </p>
              ) : (
                <div className="mt-4 space-y-3">
                  {messages.map((m) => (
                    <div
                      key={m.id}
                      className="rounded-lg border border-neutral-100 bg-neutral-50/50 p-3.5 text-[12px]"
                    >
                      <div className="mb-1 font-medium capitalize text-neutral-500 text-[11px]">
                        {m.role}
                      </div>
                      <p className="leading-relaxed text-neutral-800 whitespace-pre-wrap">
                        {m.content}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="rounded-xl border border-neutral-200 bg-white p-12 text-center">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-neutral-100 text-neutral-400">
              <MessageSquare className="h-5 w-5" />
            </div>
            <h3 className="mt-4 text-[15px] font-medium text-neutral-900">
              Session Inspector
            </h3>
            <p className="mx-auto mt-1 max-w-sm text-[12px] text-neutral-500 leading-relaxed">
              Enter a session UUID above or test an agent in the playground to inspect live voice session turns and transcripts.
            </p>
          </div>
        )}
      </div>
    </DashboardShell>
  );
}
