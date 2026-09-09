/* eslint-disable react-hooks/set-state-in-effect */
"use client";

import Link from "next/link";
import { ArrowLeft, CheckCircle2, Loader2, Play, Rocket, Sparkles } from "lucide-react";
import { useParams } from "next/navigation";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

const API_BASE_URL = "http://localhost:8000";
const PROJECT_ID = "00000000-0000-4000-8000-000000000002";

const DEFAULT_FORM = {
  name: "",
  description: "",
  tags: [] as string[],
  instructions: "You are a helpful and professional voice agent.",
  personality: "Friendly, concise, and clear.",
  locale: "en",
  llmProvider: "openai",
  llmModel: "gpt-4o-mini",
  sttProvider: "assemblyai",
  sttModel: "universal-streaming",
  ttsProvider: "elevenlabs",
  ttsVoice: "voice_default",
};

type Agent = {
  id: string;
  name: string;
  description?: string | null;
  status?: string | null;
  tags?: string[];
  created_at?: string;
  updated_at?: string;
};

type AgentVersion = {
  id: string;
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

export default function AgentOverviewPage() {
  const params = useParams<{ id: string }>();
  const agentId = params?.id ?? "";

  const [agent, setAgent] = useState<Agent | null>(null);
  const [versions, setVersions] = useState<AgentVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [form, setForm] = useState(DEFAULT_FORM);
  const [tagInput, setTagInput] = useState("");

  const draftVersion = useMemo(
    () => versions.find((version) => version.status === "draft") ?? null,
    [versions],
  );

  const loadAgentData = useCallback(async () => {
    if (!agentId) {
      setError("Missing agent id.");
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError("");

      const [agentResponse, versionsResponse] = await Promise.all([
        fetch(`${API_BASE_URL}/v1/projects/${PROJECT_ID}/agents/${agentId}`),
        fetch(`${API_BASE_URL}/v1/projects/${PROJECT_ID}/agents/${agentId}/versions`),
      ]);

      if (!agentResponse.ok) {
        throw new Error(`Unable to load agent (${agentResponse.status}).`);
      }

      if (!versionsResponse.ok) {
        throw new Error(`Unable to load agent versions (${versionsResponse.status}).`);
      }

      const agentData: Agent = await agentResponse.json();
      const versionsData: { items?: AgentVersion[] } = await versionsResponse.json();

      const latestVersion = versionsData.items?.find((item) => item.status === "draft")
        ?? versionsData.items?.[0]
        ?? null;

      setAgent(agentData);
      setVersions(versionsData.items ?? []);
      setForm({
        name: agentData.name ?? "",
        description: agentData.description ?? "",
        tags: agentData.tags ?? [],
        instructions: latestVersion?.instructions ?? DEFAULT_FORM.instructions,
        personality: latestVersion?.personality ?? DEFAULT_FORM.personality,
        locale: latestVersion?.locale ?? DEFAULT_FORM.locale,
        llmProvider: latestVersion?.llm?.provider_key ?? DEFAULT_FORM.llmProvider,
        llmModel: latestVersion?.llm?.model ?? DEFAULT_FORM.llmModel,
        sttProvider: latestVersion?.stt?.provider_key ?? DEFAULT_FORM.sttProvider,
        sttModel: latestVersion?.stt?.model ?? DEFAULT_FORM.sttModel,
        ttsProvider: latestVersion?.tts?.provider_key ?? DEFAULT_FORM.ttsProvider,
        ttsVoice: latestVersion?.tts?.voice_ref ?? DEFAULT_FORM.ttsVoice,
      });
    } catch (caughtError) {
      setError(
        caughtError instanceof Error ? caughtError.message : "Unable to load agent.",
      );
    } finally {
      setLoading(false);
    }
  }, [agentId]);

  useEffect(() => {
    void loadAgentData();
  }, [loadAgentData]);

  function updateForm<K extends keyof typeof DEFAULT_FORM>(
    field: K,
    value: (typeof DEFAULT_FORM)[K],
  ) {
    setForm((current) => ({
      ...current,
      [field]: value,
    }));
  }

  function addTag() {
    const trimmedTag = tagInput.trim();

    if (!trimmedTag || form.tags.includes(trimmedTag)) {
      setTagInput("");
      return;
    }

    updateForm("tags", [...form.tags, trimmedTag]);
    setTagInput("");
  }

  function removeTag(tagToRemove: string) {
    updateForm(
      "tags",
      form.tags.filter((tag) => tag !== tagToRemove),
    );
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!agentId) {
      setError("Missing agent id.");
      return;
    }

    if (!form.name.trim()) {
      setError("Agent name is required.");
      return;
    }

    setSaving(true);
    setError("");
    setSuccess("");

    try {
      const patchedAgentResponse = await fetch(
        `${API_BASE_URL}/v1/projects/${PROJECT_ID}/agents/${agentId}`,
        {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            name: form.name.trim(),
            description: form.description.trim(),
            tags: form.tags,
          }),
        },
      );

      if (!patchedAgentResponse.ok) {
        throw new Error(`Unable to update agent (${patchedAgentResponse.status}).`);
      }

      const versionPayload = {
        instructions: form.instructions.trim(),
        personality: form.personality.trim(),
        locale: form.locale.trim() || "en",
        llm: {
          provider_key: form.llmProvider,
          model: form.llmModel.trim(),
          params: {},
        },
        stt: {
          provider_key: form.sttProvider,
          model: form.sttModel.trim(),
          params: {},
        },
        tts: {
          provider_key: form.ttsProvider,
          voice_ref: form.ttsVoice.trim(),
          params: {},
        },
      };

      if (draftVersion?.id) {
        const patchedVersionResponse = await fetch(
          `${API_BASE_URL}/v1/projects/${PROJECT_ID}/agents/${agentId}/versions/${draftVersion.id}`,
          {
            method: "PATCH",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify(versionPayload),
          },
        );

        if (!patchedVersionResponse.ok) {
          throw new Error(
            `Unable to update draft version (${patchedVersionResponse.status}).`,
          );
        }
      } else {
        const createdVersionResponse = await fetch(
          `${API_BASE_URL}/v1/projects/${PROJECT_ID}/agents/${agentId}/versions`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify(versionPayload),
          },
        );

        if (!createdVersionResponse.ok) {
          throw new Error(
            `Unable to create draft version (${createdVersionResponse.status}).`,
          );
        }
      }

      await loadAgentData();
      setSuccess("Agent changes saved successfully.");
    } catch (caughtError) {
      setError(
        caughtError instanceof Error ? caughtError.message : "Unable to save agent.",
      );
    } finally {
      setSaving(false);
    }
  }

  async function handlePublish() {
    if (!agentId || !draftVersion?.id) return;

    setPublishing(true);
    setError("");
    setSuccess("");

    try {
      const response = await fetch(
        `${API_BASE_URL}/v1/projects/${PROJECT_ID}/agents/${agentId}/versions/${draftVersion.id}/publish`,
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

      await loadAgentData();
      setSuccess("Version published successfully. It is now active and immutable.");
    } catch (caughtError) {
      setError(
        caughtError instanceof Error ? caughtError.message : "Unable to publish version.",
      );
    } finally {
      setPublishing(false);
    }
  }

  return (
    <div className="mx-auto max-w-[1100px] px-8 py-10">
      <div className="mb-8 flex items-center justify-between gap-4">
        <Link
          href="/agents"
          className="inline-flex items-center gap-2 text-[12px] text-neutral-500 transition-colors hover:text-neutral-900"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to agents
        </Link>

        <div className="flex items-center gap-2 text-[11px] text-neutral-500">
          <Sparkles className="h-3.5 w-3.5" strokeWidth={1.8} />
          {draftVersion ? `Draft v${draftVersion.status === "draft" ? "" : ""}` : "No draft"}
        </div>
      </div>

      {loading && (
        <div className="rounded-xl border border-neutral-200 bg-neutral-50 px-4 py-10 text-center text-[12px] text-neutral-500">
          Loading agent builder...
        </div>
      )}

      {!loading && error && (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-[12px] text-red-700">
          {error}
        </div>
      )}

      {!loading && !error && agent && (
        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="rounded-xl border border-neutral-200 bg-white p-6 sm:p-8">
            <div className="mb-6 flex items-start justify-between gap-4 border-b border-neutral-200 pb-5">
              <div>
                <p className="text-[11px] font-medium uppercase tracking-[0.12em] text-neutral-400">
                  Agent overview
                </p>
                <h1 className="mt-2 text-[28px] font-semibold tracking-[-0.04em]">
                  {agent.name}
                </h1>
              </div>

              <div className="rounded-full border border-neutral-200 px-2.5 py-1 text-[10px] font-medium text-neutral-600">
                {agent.status ?? "draft"}
              </div>
            </div>

            <div className="grid gap-6 lg:grid-cols-[1.3fr_0.7fr]">
              <div className="space-y-6">
                <div>
                  <label className="mb-2 block text-[12px] font-medium text-neutral-700">
                    Agent name
                  </label>
                  <input
                    value={form.name}
                    onChange={(event) => updateForm("name", event.target.value)}
                    className="h-10 w-full rounded-lg border border-neutral-300 bg-white px-3 text-[13px] outline-none focus:border-neutral-500 focus:ring-2 focus:ring-neutral-100"
                  />
                </div>

                <div>
                  <label className="mb-2 block text-[12px] font-medium text-neutral-700">
                    Description
                  </label>
                  <textarea
                    value={form.description}
                    onChange={(event) => updateForm("description", event.target.value)}
                    rows={4}
                    className="w-full resize-none rounded-lg border border-neutral-300 bg-white px-3 py-2.5 text-[13px] leading-6 outline-none focus:border-neutral-500 focus:ring-2 focus:ring-neutral-100"
                  />
                </div>

                <div>
                  <label className="mb-2 block text-[12px] font-medium text-neutral-700">
                    Tags
                  </label>
                  <div className="rounded-lg border border-neutral-300 px-2 py-2">
                    <div className="flex flex-wrap items-center gap-2">
                      {form.tags.map((tag) => (
                        <span
                          key={tag}
                          className="inline-flex items-center gap-1 rounded-full border border-neutral-200 bg-neutral-100 px-2 py-1 text-[10px] font-medium text-neutral-700"
                        >
                          {tag}
                          <button
                            type="button"
                            onClick={() => removeTag(tag)}
                            className="text-neutral-500 transition-colors hover:text-neutral-900"
                          >
                            ×
                          </button>
                        </span>
                      ))}

                      <input
                        value={tagInput}
                        onChange={(event) => setTagInput(event.target.value)}
                        onKeyDown={(event) => {
                          if (event.key === "Enter" || event.key === ",") {
                            event.preventDefault();
                            addTag();
                          }
                        }}
                        onBlur={addTag}
                        placeholder={form.tags.length === 0 ? "Add tag..." : "Add another..."}
                        className="min-w-[120px] flex-1 border-0 bg-transparent px-1 text-[12px] outline-none placeholder:text-neutral-400"
                      />
                    </div>
                  </div>
                </div>
              </div>

              <div className="rounded-xl border border-neutral-200 bg-neutral-50 p-4">
                <p className="text-[11px] font-medium uppercase tracking-[0.12em] text-neutral-400">
                  Summary
                </p>

                <dl className="mt-4 space-y-3 text-[12px] text-neutral-600">
                  <div>
                    <dt className="text-neutral-400">Created</dt>
                    <dd className="mt-1 font-medium text-neutral-700">
                      {formatDate(agent.created_at)}
                    </dd>
                  </div>

                  <div>
                    <dt className="text-neutral-400">Updated</dt>
                    <dd className="mt-1 font-medium text-neutral-700">
                      {formatDate(agent.updated_at)}
                    </dd>
                  </div>

                  <div>
                    <dt className="text-neutral-400">Version</dt>
                    <dd className="mt-1 font-medium text-neutral-700">
                      {draftVersion ? `Draft (${draftVersion.status})` : "Not created yet"}
                    </dd>
                  </div>
                </dl>
              </div>
            </div>
          </div>

          <div className="rounded-xl border border-neutral-200 bg-white p-6 sm:p-8">
            <div className="mb-5">
              <p className="text-[11px] font-medium uppercase tracking-[0.12em] text-neutral-400">
                Behavior
              </p>
              <h2 className="mt-2 text-[20px] font-semibold tracking-[-0.03em]">
                Agent configuration
              </h2>
            </div>

            <div className="grid gap-6 lg:grid-cols-2">
              <div>
                <label className="mb-2 block text-[12px] font-medium text-neutral-700">
                  Instructions
                </label>
                <textarea
                  value={form.instructions}
                  onChange={(event) => updateForm("instructions", event.target.value)}
                  rows={6}
                  className="w-full resize-none rounded-lg border border-neutral-300 bg-white px-3 py-2.5 text-[13px] leading-6 outline-none focus:border-neutral-500 focus:ring-2 focus:ring-neutral-100"
                />
              </div>

              <div>
                <label className="mb-2 block text-[12px] font-medium text-neutral-700">
                  Personality
                </label>
                <textarea
                  value={form.personality}
                  onChange={(event) => updateForm("personality", event.target.value)}
                  rows={6}
                  className="w-full resize-none rounded-lg border border-neutral-300 bg-white px-3 py-2.5 text-[13px] leading-6 outline-none focus:border-neutral-500 focus:ring-2 focus:ring-neutral-100"
                />
              </div>
            </div>

            <div className="mt-6 grid gap-6 lg:grid-cols-3">
              <div>
                <label className="mb-2 block text-[12px] font-medium text-neutral-700">
                  Locale
                </label>
                <input
                  value={form.locale}
                  onChange={(event) => updateForm("locale", event.target.value)}
                  className="h-10 w-full rounded-lg border border-neutral-300 bg-white px-3 text-[13px] outline-none focus:border-neutral-500 focus:ring-2 focus:ring-neutral-100"
                />
              </div>

              <div>
                <label className="mb-2 block text-[12px] font-medium text-neutral-700">
                  LLM provider
                </label>
                <select
                  value={form.llmProvider}
                  onChange={(event) => updateForm("llmProvider", event.target.value)}
                  className="h-10 w-full rounded-lg border border-neutral-300 bg-white px-3 text-[13px] outline-none focus:border-neutral-500 focus:ring-2 focus:ring-neutral-100"
                >
                  <option value="openai">OpenAI</option>
                </select>
              </div>

              <div>
                <label className="mb-2 block text-[12px] font-medium text-neutral-700">
                  LLM model
                </label>
                <input
                  value={form.llmModel}
                  onChange={(event) => updateForm("llmModel", event.target.value)}
                  className="h-10 w-full rounded-lg border border-neutral-300 bg-white px-3 text-[13px] outline-none focus:border-neutral-500 focus:ring-2 focus:ring-neutral-100"
                />
              </div>

              <div>
                <label className="mb-2 block text-[12px] font-medium text-neutral-700">
                  STT provider
                </label>
                <select
                  value={form.sttProvider}
                  onChange={(event) => updateForm("sttProvider", event.target.value)}
                  className="h-10 w-full rounded-lg border border-neutral-300 bg-white px-3 text-[13px] outline-none focus:border-neutral-500 focus:ring-2 focus:ring-neutral-100"
                >
                  <option value="assemblyai">AssemblyAI</option>
                </select>
              </div>

              <div>
                <label className="mb-2 block text-[12px] font-medium text-neutral-700">
                  STT model
                </label>
                <input
                  value={form.sttModel}
                  onChange={(event) => updateForm("sttModel", event.target.value)}
                  className="h-10 w-full rounded-lg border border-neutral-300 bg-white px-3 text-[13px] outline-none focus:border-neutral-500 focus:ring-2 focus:ring-neutral-100"
                />
              </div>

              <div>
                <label className="mb-2 block text-[12px] font-medium text-neutral-700">
                  TTS provider
                </label>
                <select
                  value={form.ttsProvider}
                  onChange={(event) => updateForm("ttsProvider", event.target.value)}
                  className="h-10 w-full rounded-lg border border-neutral-300 bg-white px-3 text-[13px] outline-none focus:border-neutral-500 focus:ring-2 focus:ring-neutral-100"
                >
                  <option value="elevenlabs">ElevenLabs</option>
                </select>
              </div>

              <div className="lg:col-span-2">
                <label className="mb-2 block text-[12px] font-medium text-neutral-700">
                  TTS voice reference
                </label>
                <input
                  value={form.ttsVoice}
                  onChange={(event) => updateForm("ttsVoice", event.target.value)}
                  className="h-10 w-full rounded-lg border border-neutral-300 bg-white px-3 text-[13px] outline-none focus:border-neutral-500 focus:ring-2 focus:ring-neutral-100"
                />
              </div>
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-neutral-200 bg-white p-4">
            <div className="text-[12px] text-neutral-500">
              {success && (
                <span className="inline-flex items-center gap-2 text-emerald-600">
                  <CheckCircle2 className="h-4 w-4" />
                  {success}
                </span>
              )}
            </div>

            <div className="flex items-center gap-3">
              <Link
                href={`/agents/${agentId}/playground`}
                className="inline-flex h-10 items-center gap-1.5 rounded-lg border border-neutral-200 bg-white px-3.5 text-[12px] font-medium text-neutral-700 transition-colors hover:bg-neutral-50 hover:text-neutral-950"
              >
                <Play className="h-3.5 w-3.5 fill-current" />
                Playground
              </Link>

              {draftVersion && (
                <button
                  type="button"
                  onClick={handlePublish}
                  disabled={publishing || saving}
                  className="inline-flex h-10 items-center gap-1.5 rounded-lg border border-neutral-300 bg-white px-3.5 text-[12px] font-medium text-neutral-800 transition-colors hover:bg-neutral-50 disabled:cursor-not-allowed disabled:text-neutral-400"
                >
                  {publishing ? (
                    <>
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      Publishing...
                    </>
                  ) : (
                    <>
                      <Rocket className="h-3.5 w-3.5" />
                      Publish draft
                    </>
                  )}
                </button>
              )}

              <button
                type="submit"
                disabled={saving || !form.name.trim()}
                className="inline-flex h-10 items-center gap-2 rounded-lg bg-neutral-950 px-4 text-[12px] font-medium text-white transition-colors hover:bg-neutral-800 disabled:cursor-not-allowed disabled:bg-neutral-300"
              >
                {saving ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Saving...
                  </>
                ) : (
                  "Save draft"
                )}
              </button>
            </div>
          </div>
        </form>
      )}
    </div >
  );
}
