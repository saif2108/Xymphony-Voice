"use client";

import { useState } from "react";
import { BookOpen, Plus, FileText, Database, CheckCircle2, Trash2 } from "lucide-react";

interface KnowledgeDoc {
  id: string;
  title: string;
  type: "document" | "faq" | "snippet";
  charCount: number;
  updatedAt: string;
}

const INITIAL_DOCS: KnowledgeDoc[] = [
  {
    id: "doc-1",
    title: "Company Return & Refund Policy 2026.pdf",
    type: "document",
    charCount: 4250,
    updatedAt: "Sep 8, 2026",
  },
  {
    id: "doc-2",
    title: "Product Warranty & Coverage Tiers",
    type: "faq",
    charCount: 1840,
    updatedAt: "Sep 9, 2026",
  },
];

export default function KnowledgePage() {
  const [docs, setDocs] = useState<KnowledgeDoc[]>(INITIAL_DOCS);
  const [isAdding, setIsAdding] = useState(false);
  const [docTitle, setDocTitle] = useState("");
  const [docContent, setDocContent] = useState("");
  const [error, setError] = useState("");

  function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!docTitle.trim() || !docContent.trim()) {
      setError("Document title and content are required.");
      return;
    }

    const newDoc: KnowledgeDoc = {
      id: `doc-${Date.now()}`,
      title: docTitle.trim(),
      type: "document",
      charCount: docContent.trim().length,
      updatedAt: "Just now",
    };

    setDocs((prev) => [newDoc, ...prev]);
    setIsAdding(false);
    setDocTitle("");
    setDocContent("");
    setError("");
  }

  function handleDelete(id: string) {
    setDocs((prev) => prev.filter((d) => d.id !== id));
  }

  return (
    <div className="mx-auto max-w-[1100px] px-8 py-10">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-[0.12em] text-neutral-400">
            Agent context
          </p>
          <h2 className="mt-2 text-[22px] font-semibold tracking-[-0.03em]">
            Knowledge Base
          </h2>
          <p className="mt-1 text-[13px] text-neutral-500">
            Add internal knowledge, company policies, or product specs to ground your agent in real-time answers.
          </p>
        </div>

        <button
          onClick={() => setIsAdding(!isAdding)}
          className="flex h-9 items-center gap-1.5 rounded-lg bg-neutral-950 px-3.5 text-[12px] font-medium text-white transition-colors hover:bg-neutral-800"
        >
          <Plus className="h-3.5 w-3.5" />
          Add knowledge
        </button>
      </div>

      {isAdding && (
        <form
          onSubmit={handleAdd}
          className="mb-6 rounded-xl border border-neutral-300 bg-white p-6 shadow-sm"
        >
          <h3 className="text-[14px] font-semibold text-neutral-900">
            Add Knowledge Document
          </h3>
          <p className="mt-1 text-[12px] text-neutral-500">
            Content will be chunked and indexed in PostgreSQL pgvector.
          </p>

          {error && (
            <div className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-700">
              {error}
            </div>
          )}

          <div className="mt-4">
            <label className="mb-1.5 block text-[12px] font-medium text-neutral-700">
              Title / Name
            </label>
            <input
              type="text"
              placeholder="e.g. Return Policy FAQ"
              value={docTitle}
              onChange={(e) => setDocTitle(e.target.value)}
              className="h-10 w-full rounded-lg border border-neutral-300 bg-white px-3 text-[13px] outline-none focus:border-neutral-500 focus:ring-2 focus:ring-neutral-100"
            />
          </div>

          <div className="mt-4">
            <label className="mb-1.5 block text-[12px] font-medium text-neutral-700">
              Text Content
            </label>
            <textarea
              rows={6}
              placeholder="Paste article, guideline, or FAQ content..."
              value={docContent}
              onChange={(e) => setDocContent(e.target.value)}
              className="w-full rounded-lg border border-neutral-300 bg-white p-3 text-[13px] leading-relaxed outline-none focus:border-neutral-500 focus:ring-2 focus:ring-neutral-100"
            />
          </div>

          <div className="mt-4 flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={() => setIsAdding(false)}
              className="h-8 rounded-lg px-3 text-[12px] text-neutral-500 hover:bg-neutral-100"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="flex h-8 items-center gap-1.5 rounded-lg bg-neutral-950 px-3 text-[12px] font-medium text-white hover:bg-neutral-800"
            >
              Index Document
            </button>
          </div>
        </form>
      )}

      {/* Docs List */}
      <div className="space-y-3">
        {docs.map((doc) => (
          <div
            key={doc.id}
            className="flex items-center justify-between rounded-xl border border-neutral-200 bg-white p-5 transition-shadow hover:shadow-sm"
          >
            <div className="flex items-center gap-3.5">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-neutral-200 bg-neutral-50 text-neutral-600">
                <FileText className="h-4 w-4" />
              </div>
              <div>
                <span className="text-[13px] font-medium text-neutral-900">
                  {doc.title}
                </span>
                <p className="mt-0.5 text-[11px] text-neutral-400">
                  {doc.charCount.toLocaleString()} chars · Updated {doc.updatedAt}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-600">
                <CheckCircle2 className="h-3.5 w-3.5" />
                Indexed
              </span>
              <button
                type="button"
                onClick={() => handleDelete(doc.id)}
                className="flex h-8 w-8 items-center justify-center rounded-lg text-neutral-400 hover:bg-neutral-50 hover:text-red-600 transition-colors"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-8 rounded-xl border border-neutral-200 bg-neutral-50/60 p-5">
        <div className="flex items-center gap-2 text-[12px] font-semibold text-neutral-800">
          <Database className="h-4 w-4 text-neutral-600" />
          pgvector Semantic Retrieval
        </div>
        <p className="mt-1 text-[12px] text-neutral-500 leading-relaxed">
          Knowledge chunks are stored and queried using cosine similarity in PostgreSQL pgvector. Relevant excerpts are injected into the agent&apos;s turn context window dynamically.
        </p>
      </div>
    </div>
  );
}
