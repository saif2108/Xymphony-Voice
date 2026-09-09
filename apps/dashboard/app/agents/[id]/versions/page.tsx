/* eslint-disable react-hooks/set-state-in-effect */
"use client";

import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import {
  CheckCircle2,
  Circle,
  Clock,
  Loader2,
  Rocket,
  Shield,
} from "lucide-react";

const API_BASE_URL = "http://localhost:8000";
const PROJECT_ID = "00000000-0000-4000-8000-000000000002";

type AgentVersion = {
  id: string;
  version_n: number;
  status: string;
  instructions: string;
  personality: string;
  locale: string;
  llm?: {
    provider_key?: string;
    model?: string;
    params?: Record<string, unknown>;
  };
  stt?: {
    provider_key?: string;
    model?: string;
    params?: Record<string, unknown>;
  };
  tts?: {
    provider_key?: string;
    voice_ref?: string;
    params?: Record<string, unknown>;
  };
  config_hash?: string;
  created_at?: string;
  published_at?: string;
};

function formatDateTime(value?: string | null) {
  if (!value) return "—";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "—";
  }

  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

export default function VersionsPage() {
  const params = useParams<{ id: string }>();
  const agentId = params?.id ?? "";

  const [versions, setVersions] = useState<AgentVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [publishing, setPublishing] = useState<string | null>(null);
  const [publishSuccess, setPublishSuccess] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const loadVersions = useCallback(async () => {
    if (!agentId) {
      setError("Missing agent id.");
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError("");

      const response = await fetch(
        `${API_BASE_URL}/v1/projects/${PROJECT_ID}/agents/${agentId}/versions`
      );

      if (!response.ok) {
        throw new Error(`Unable to load versions (${response.status}).`);
      }

      const data: { items?: AgentVersion[] } = await response.json();
      setVersions(data.items ?? []);
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "Unable to load versions."
      );
    } finally {
      setLoading(false);
    }
  }, [agentId]);

  useEffect(() => {
    void loadVersions();
  }, [loadVersions]);

  async function handlePublish(versionId: string) {
    if (!agentId) return;

    setPublishing(versionId);
    setPublishSuccess("");
    setError("");

    try {
      const response = await fetch(
        `${API_BASE_URL}/v1/projects/${PROJECT_ID}/agents/${agentId}/versions/${versionId}/publish`,
        { method: "POST" }
      );

      if (!response.ok) {
        let message = "Unable to publish version.";

        try {
          const data = await response.json();

          if (typeof data?.message === "string") {
            message = data.message;
          }
        } catch {
          // Keep default message.
        }

        throw new Error(message);
      }

      setPublishSuccess("Version published successfully.");
      await loadVersions();
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "Unable to publish version."
      );
    } finally {
      setPublishing(null);
    }
  }

  return (
    <div className="mx-auto max-w-[1100px] px-8 py-10">
      <div className="mb-6">
        <p className="text-[11px] font-medium uppercase tracking-[0.12em] text-neutral-400">
          Agent configuration
        </p>
        <h2 className="mt-2 text-[22px] font-semibold tracking-[-0.03em]">
          Version history
        </h2>
        <p className="mt-1 text-[13px] text-neutral-500">
          Track configuration changes. Published versions are immutable and used
          in live sessions.
        </p>
      </div>

      {publishSuccess && (
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-[12px] text-emerald-700">
          <CheckCircle2 className="h-4 w-4 shrink-0" />
          {publishSuccess}
        </div>
      )}

      {error && !loading && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-[12px] text-red-700">
          {error}
        </div>
      )}

      {loading && (
        <div className="rounded-xl border border-neutral-200 bg-neutral-50 px-4 py-14 text-center text-[12px] text-neutral-500">
          Loading versions...
        </div>
      )}

      {!loading && !error && versions.length === 0 && (
        <div className="rounded-xl border border-neutral-200 bg-white px-4 py-14 text-center">
          <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-full bg-neutral-100">
            <Clock className="h-4 w-4 text-neutral-400" />
          </div>
          <p className="mt-4 text-[13px] font-medium text-neutral-700">
            No versions yet
          </p>
          <p className="mt-1 text-[12px] text-neutral-400">
            Save a draft from the Overview tab to create the first version.
          </p>
        </div>
      )}

      {!loading && versions.length > 0 && (
        <div className="space-y-3">
          {versions.map((version) => {
            const isDraft = version.status === "draft";
            const isPublished = version.status === "published";
            const isExpanded = expandedId === version.id;
            const isBeingPublished = publishing === version.id;

            return (
              <div
                key={version.id}
                className="rounded-xl border border-neutral-200 bg-white transition-shadow hover:shadow-sm"
              >
                <button
                  type="button"
                  onClick={() =>
                    setExpandedId(isExpanded ? null : version.id)
                  }
                  className="flex w-full items-center justify-between gap-4 px-6 py-5 text-left"
                >
                  <div className="flex items-center gap-4">
                    <div
                      className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full ${
                        isPublished
                          ? "bg-emerald-50 text-emerald-600"
                          : "bg-neutral-100 text-neutral-500"
                      }`}
                    >
                      {isPublished ? (
                        <CheckCircle2 className="h-4 w-4" />
                      ) : (
                        <Circle className="h-4 w-4" />
                      )}
                    </div>

                    <div>
                      <div className="flex items-center gap-2">
                        <p className="text-[13px] font-semibold">
                          Version {version.version_n}
                        </p>

                        <span
                          className={`rounded-full border px-2 py-0.5 text-[10px] font-medium ${
                            isPublished
                              ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                              : "border-neutral-200 bg-neutral-50 text-neutral-600"
                          }`}
                        >
                          {version.status}
                        </span>
                      </div>

                      <p className="mt-1 text-[11px] text-neutral-400">
                        Created {formatDateTime(version.created_at)}
                        {version.published_at &&
                          ` · Published ${formatDateTime(version.published_at)}`}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-3">
                    {isDraft && (
                      <button
                        type="button"
                        onClick={(event) => {
                          event.stopPropagation();
                          handlePublish(version.id);
                        }}
                        disabled={isBeingPublished}
                        className="flex h-8 items-center gap-1.5 rounded-lg bg-neutral-950 px-3 text-[11px] font-medium text-white transition-colors hover:bg-neutral-800 disabled:cursor-not-allowed disabled:bg-neutral-300"
                      >
                        {isBeingPublished ? (
                          <>
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                            Publishing...
                          </>
                        ) : (
                          <>
                            <Rocket className="h-3.5 w-3.5" />
                            Publish
                          </>
                        )}
                      </button>
                    )}

                    {isPublished && (
                      <div className="flex items-center gap-1.5 text-[11px] text-emerald-600">
                        <Shield className="h-3.5 w-3.5" />
                        Immutable
                      </div>
                    )}

                    <span className="text-[14px] text-neutral-300 transition-transform">
                      {isExpanded ? "−" : "+"}
                    </span>
                  </div>
                </button>

                {isExpanded && (
                  <div className="border-t border-neutral-100 px-6 py-5">
                    <div className="grid gap-5 lg:grid-cols-2">
                      <div>
                        <p className="mb-1.5 text-[11px] font-medium uppercase tracking-[0.1em] text-neutral-400">
                          Instructions
                        </p>
                        <p className="whitespace-pre-wrap rounded-lg border border-neutral-100 bg-neutral-50 px-3 py-2.5 text-[12px] leading-relaxed text-neutral-700">
                          {version.instructions || "—"}
                        </p>
                      </div>

                      <div>
                        <p className="mb-1.5 text-[11px] font-medium uppercase tracking-[0.1em] text-neutral-400">
                          Personality
                        </p>
                        <p className="whitespace-pre-wrap rounded-lg border border-neutral-100 bg-neutral-50 px-3 py-2.5 text-[12px] leading-relaxed text-neutral-700">
                          {version.personality || "—"}
                        </p>
                      </div>
                    </div>

                    <div className="mt-5 grid grid-cols-2 gap-4 lg:grid-cols-4">
                      <div>
                        <p className="text-[10px] font-medium uppercase tracking-[0.1em] text-neutral-400">
                          Locale
                        </p>
                        <p className="mt-1 text-[12px] font-medium text-neutral-700">
                          {version.locale || "en"}
                        </p>
                      </div>

                      <div>
                        <p className="text-[10px] font-medium uppercase tracking-[0.1em] text-neutral-400">
                          LLM
                        </p>
                        <p className="mt-1 text-[12px] font-medium text-neutral-700">
                          {version.llm?.provider_key ?? "—"} /{" "}
                          {version.llm?.model ?? "—"}
                        </p>
                      </div>

                      <div>
                        <p className="text-[10px] font-medium uppercase tracking-[0.1em] text-neutral-400">
                          STT
                        </p>
                        <p className="mt-1 text-[12px] font-medium text-neutral-700">
                          {version.stt?.provider_key ?? "—"} /{" "}
                          {version.stt?.model ?? "—"}
                        </p>
                      </div>

                      <div>
                        <p className="text-[10px] font-medium uppercase tracking-[0.1em] text-neutral-400">
                          TTS
                        </p>
                        <p className="mt-1 text-[12px] font-medium text-neutral-700">
                          {version.tts?.provider_key ?? "—"} /{" "}
                          {version.tts?.voice_ref ?? "—"}
                        </p>
                      </div>
                    </div>

                    {version.config_hash && (
                      <div className="mt-4 border-t border-neutral-100 pt-3">
                        <p className="text-[10px] text-neutral-400">
                          Config hash:{" "}
                          <code className="font-mono text-neutral-500">
                            {version.config_hash}
                          </code>
                        </p>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
