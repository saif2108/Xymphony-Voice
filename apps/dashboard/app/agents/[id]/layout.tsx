"use client";

import { useEffect, useState } from "react";
import { useParams, usePathname } from "next/navigation";
import Link from "next/link";
import DashboardShell from "../../components/dashboard-shell";

const API_BASE_URL = "http://localhost:8000";
const PROJECT_ID = "00000000-0000-4000-8000-000000000002";

const TABS = [
  { label: "Overview", href: "overview" },
  { label: "Voice", href: "voice" },
  { label: "Knowledge", href: "knowledge" },
  { label: "Tools", href: "tools" },
  { label: "Playground", href: "playground" },
  { label: "Versions", href: "versions" },
];

export default function AgentLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const params = useParams<{ id: string }>();
  const pathname = usePathname();
  const agentId = params?.id ?? "";

  const [agentName, setAgentName] = useState<string>("Agent");

  useEffect(() => {
    if (!agentId) return;
    fetch(`${API_BASE_URL}/v1/projects/${PROJECT_ID}/agents/${agentId}`)
      .then((res) => {
        if (!res.ok) throw new Error("Failed");
        return res.json();
      })
      .then((data) => {
        if (data?.name) setAgentName(data.name);
      })
      .catch(() => {
        // Fallback to default
      });
  }, [agentId]);

  return (
    <DashboardShell breadcrumb={agentName} showCreateAgent={false}>
      <div className="border-b border-neutral-200 bg-white px-8 pt-6">
        <div className="flex gap-6">
          {TABS.map((tab) => {
            const href = `/agents/${agentId}/${tab.href}`;
            const isActive = pathname === href || pathname.startsWith(`${href}/`);

            return (
              <Link
                key={tab.href}
                href={href}
                className={`border-b-2 pb-3 text-[13px] font-medium transition-colors ${
                  isActive
                    ? "border-neutral-950 text-neutral-950"
                    : "border-transparent text-neutral-500 hover:text-neutral-900"
                }`}
              >
                {tab.label}
              </Link>
            );
          })}
        </div>
      </div>
      <div className="min-h-[calc(100vh-120px)] bg-neutral-50/30">
        {children}
      </div>
    </DashboardShell>
  );
}
