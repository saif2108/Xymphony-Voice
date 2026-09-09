"use client";

import { FormEvent, useState } from "react";
import { ArrowLeft, Plus, X } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

const PROJECT_ID = "00000000-0000-4000-8000-000000000002";
const API_BASE_URL = "http://localhost:8000";

export default function NewAgentPage() {
  const router = useRouter();

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [tagInput, setTagInput] = useState("");
  const [tags, setTags] = useState<string[]>([]);
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState("");


  function addTag() {
    const tag = tagInput.trim();

    if (!tag || tags.includes(tag)) {
      setTagInput("");
      return;
    }

    setTags((current) => [...current, tag]);
    setTagInput("");
  }

  function removeTag(tagToRemove: string) {
    setTags((current) => current.filter((tag) => tag !== tagToRemove));
  }

  function handleTagKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter" || event.key === ",") {
      event.preventDefault();
      addTag();
    }

    if (event.key === "Backspace" && !tagInput && tags.length > 0) {
      setTags((current) => current.slice(0, -1));
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const trimmedName = name.trim();

    if (!trimmedName) {
      setError("Agent name is required.");
      return;
    }

    setError("");
    setIsCreating(true);

    try {
      const response = await fetch(
        `${API_BASE_URL}/v1/projects/${PROJECT_ID}/agents`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            name: trimmedName,
            description: description.trim(),
            status: "draft",
            tags,
          }),
        },
      );

      if (!response.ok) {
        let message = "Unable to create agent.";

        try {
          const data = await response.json();

          if (typeof data?.message === "string") {
            message = data.message;
          } else if (typeof data?.detail === "string") {
            message = data.detail;
          } else if (Array.isArray(data?.detail)) {
            message = data.detail
              .map((item: { msg?: string }) => item.msg)
              .filter(Boolean)
              .join(", ");
          }
        } catch {
          // Keep the default error message.
        }

        throw new Error(message);
      }

      const agent = await response.json();

      router.push(`/agents/${agent.id}/overview`);
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "Unable to create agent.",
      );
      setIsCreating(false);
    }
  }

  return (
    <main className="min-h-screen bg-white text-zinc-950">
      <div className="mx-auto w-full max-w-3xl px-6 py-10 sm:px-8">
        <Link
          href="/agents"
          className="mb-10 inline-flex items-center gap-2 text-sm text-zinc-500 transition-colors hover:text-zinc-950"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to agents
        </Link>

        <div className="mb-8">
          <p className="mb-2 text-sm font-medium text-zinc-500">
            New agent
          </p>

          <h1 className="text-2xl font-semibold tracking-tight">
            Create an agent
          </h1>

          <p className="mt-2 text-sm leading-6 text-zinc-500">
            Start with the basics. You can configure the agent&apos;s behavior
            and voice after creating it.
          </p>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="rounded-xl border border-zinc-200 bg-white">
            <div className="space-y-7 p-6 sm:p-8">
              <div>
                <label
                  htmlFor="agent-name"
                  className="mb-2 block text-sm font-medium"
                >
                  Agent name
                </label>

                <input
                  id="agent-name"
                  type="text"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  placeholder="e.g. Customer Support"
                  maxLength={200}
                  autoFocus
                  disabled={isCreating}
                  className="h-10 w-full rounded-lg border border-zinc-300 bg-white px-3 text-sm outline-none transition-colors placeholder:text-zinc-400 focus:border-zinc-500 focus:ring-2 focus:ring-zinc-100 disabled:bg-zinc-50"
                />

                <p className="mt-2 text-xs text-zinc-400">
                  Give your agent a name that clearly identifies its purpose.
                </p>
              </div>

              <div>
                <label
                  htmlFor="agent-description"
                  className="mb-2 block text-sm font-medium"
                >
                  Description
                  <span className="ml-1 font-normal text-zinc-400">
                    Optional
                  </span>
                </label>

                <textarea
                  id="agent-description"
                  value={description}
                  onChange={(event) => setDescription(event.target.value)}
                  placeholder="Briefly describe what this agent is responsible for."
                  maxLength={4000}
                  rows={4}
                  disabled={isCreating}
                  className="w-full resize-none rounded-lg border border-zinc-300 bg-white px-3 py-2.5 text-sm leading-6 outline-none transition-colors placeholder:text-zinc-400 focus:border-zinc-500 focus:ring-2 focus:ring-zinc-100 disabled:bg-zinc-50"
                />

                <div className="mt-2 flex justify-end text-xs text-zinc-400">
                  {description.length}/4000
                </div>
              </div>

              <div>
                <label
                  htmlFor="agent-tags"
                  className="mb-2 block text-sm font-medium"
                >
                  Tags
                  <span className="ml-1 font-normal text-zinc-400">
                    Optional
                  </span>
                </label>

                <div className="min-h-10 rounded-lg border border-zinc-300 px-2 py-1.5 focus-within:border-zinc-500 focus-within:ring-2 focus-within:ring-zinc-100">
                  <div className="flex flex-wrap items-center gap-1.5">
                    {tags.map((tag) => (
                      <span
                        key={tag}
                        className="inline-flex items-center gap-1 rounded-md bg-zinc-100 px-2 py-1 text-xs font-medium text-zinc-700"
                      >
                        {tag}

                        <button
                          type="button"
                          onClick={() => removeTag(tag)}
                          disabled={isCreating}
                          aria-label={`Remove ${tag}`}
                          className="text-zinc-400 hover:text-zinc-700"
                        >
                          <X className="h-3 w-3" />
                        </button>
                      </span>
                    ))}

                    <input
                      id="agent-tags"
                      type="text"
                      value={tagInput}
                      onChange={(event) => setTagInput(event.target.value)}
                      onKeyDown={handleTagKeyDown}
                      onBlur={addTag}
                      placeholder={
                        tags.length === 0 ? "Add tags..." : "Add another..."
                      }
                      disabled={isCreating}
                      className="h-7 min-w-32 flex-1 border-0 bg-transparent px-1 text-sm outline-none placeholder:text-zinc-400"
                    />
                  </div>
                </div>

                <p className="mt-2 text-xs text-zinc-400">
                  Press Enter to add a tag.
                </p>
              </div>

              {error && (
                <div
                  role="alert"
                  className="rounded-lg border border-red-200 bg-red-50 px-3 py-2.5 text-sm text-red-700"
                >
                  {error}
                </div>
              )}
            </div>

            <div className="flex items-center justify-end gap-3 border-t border-zinc-200 bg-zinc-50/50 px-6 py-4 sm:px-8">
              <Link
                href="/agents"
                className="inline-flex h-9 items-center rounded-lg px-3 text-sm font-medium text-zinc-600 transition-colors hover:bg-zinc-100 hover:text-zinc-950"
              >
                Cancel
              </Link>

              <button
                type="submit"
                disabled={isCreating || !name.trim()}
                className="inline-flex h-9 items-center gap-2 rounded-lg bg-zinc-950 px-4 text-sm font-medium text-white transition-colors hover:bg-zinc-800 disabled:cursor-not-allowed disabled:bg-zinc-300"
              >
                <Plus className="h-4 w-4" />
                {isCreating ? "Creating..." : "Create agent"}
              </button>
            </div>
          </div>
        </form>
      </div>
    </main>
  );
}