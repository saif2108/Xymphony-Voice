
import Link from "next/link";
import {
  Activity,
  Code2,
  LayoutDashboard,
  MessageSquare,
  Plus,
  Settings,
  Sparkles,
  Users,
} from "lucide-react";

const navigation = [
  { label: "Overview", href: "/", icon: LayoutDashboard },
  { label: "Agents", href: "/agents", icon: Sparkles },
  { label: "Sessions", href: "/sessions", icon: MessageSquare },
  { label: "Analytics", href: "/analytics", icon: Activity },
];

export default function Home() {
  return (
    <div className="min-h-screen bg-white text-neutral-950">
      <div className="flex min-h-screen">
        <aside className="flex w-[224px] shrink-0 flex-col border-r border-neutral-200 bg-white">
          <div className="flex h-14 items-center border-b border-neutral-200 px-5">
            <Link
              href="/"
              className="text-[15px] font-semibold tracking-[-0.02em]"
            >
              Xymphony
            </Link>
          </div>

          <div className="px-3 py-4">
            <button className="flex w-full items-center gap-3 rounded-md px-2.5 py-2 text-left transition-colors hover:bg-neutral-50">
              <div className="flex h-7 w-7 items-center justify-center rounded-md border border-neutral-200 text-[11px] font-semibold">
                X
              </div>

              <div className="min-w-0">
                <p className="truncate text-[12px] font-medium">
                  My Workspace
                </p>
                <p className="mt-0.5 text-[11px] text-neutral-500">
                  Development
                </p>
              </div>
            </button>
          </div>

          <nav className="px-3">
            <p className="px-2.5 pb-2 text-[10px] font-medium uppercase tracking-[0.12em] text-neutral-400">
              Workspace
            </p>

            <div className="space-y-0.5">
              {navigation.map((item) => {
                const Icon = item.icon;
                const active = item.href === "/";

                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`flex h-8 items-center gap-2.5 rounded-md px-2.5 text-[12px] transition-colors ${
                      active
                        ? "bg-neutral-100 font-medium text-neutral-950"
                        : "text-neutral-500 hover:bg-neutral-50 hover:text-neutral-900"
                    }`}
                  >
                    <Icon className="h-3.5 w-3.5" strokeWidth={1.8} />
                    {item.label}
                  </Link>
                );
              })}
            </div>

            <p className="px-2.5 pb-2 pt-8 text-[10px] font-medium uppercase tracking-[0.12em] text-neutral-400">
              Developer
            </p>

            <div className="space-y-0.5">
              <Link
                href="#"
                className="flex h-8 items-center gap-2.5 rounded-md px-2.5 text-[12px] text-neutral-500 transition-colors hover:bg-neutral-50 hover:text-neutral-900"
              >
                <Code2 className="h-3.5 w-3.5" strokeWidth={1.8} />
                API
              </Link>

              <Link
                href="#"
                className="flex h-8 items-center gap-2.5 rounded-md px-2.5 text-[12px] text-neutral-500 transition-colors hover:bg-neutral-50 hover:text-neutral-900"
              >
                <Users className="h-3.5 w-3.5" strokeWidth={1.8} />
                Members
              </Link>
            </div>
          </nav>

          <div className="mt-auto border-t border-neutral-200 p-3">
            <Link
              href="#"
              className="flex h-8 items-center gap-2.5 rounded-md px-2.5 text-[12px] text-neutral-500 transition-colors hover:bg-neutral-50 hover:text-neutral-900"
            >
              <Settings className="h-3.5 w-3.5" strokeWidth={1.8} />
              Settings
            </Link>

            <div className="mt-2 flex items-center gap-2.5 border-t border-neutral-100 px-2.5 pt-3">
              <div className="flex h-7 w-7 items-center justify-center rounded-full border border-neutral-200 text-[10px] font-medium">
                R
              </div>

              <div>
                <p className="text-[11px] font-medium">Developer</p>
                <p className="mt-0.5 text-[10px] text-neutral-400">
                  Local account
                </p>
              </div>
            </div>
          </div>
        </aside>

        <main className="min-w-0 flex-1">
          <header className="flex h-14 items-center justify-between border-b border-neutral-200 px-8">
            <div className="flex items-center gap-2 text-[12px]">
              <span className="text-neutral-400">My Workspace</span>
              <span className="text-neutral-300">/</span>
              <span className="text-neutral-700">Overview</span>
            </div>

            <Link
              href="/agents/new"
              className="flex h-8 items-center gap-1.5 rounded-md bg-neutral-950 px-3 text-[11px] font-medium text-white transition-colors hover:bg-neutral-800"
            >
              <Plus className="h-3.5 w-3.5" />
              Create agent
            </Link>
          </header>

          <div className="mx-auto max-w-[1080px] px-8 py-12">
            <div className="border-b border-neutral-200 pb-8">
              <p className="text-[11px] font-medium uppercase tracking-[0.1em] text-neutral-400">
                Workspace
              </p>

              <h1 className="mt-2 text-[28px] font-semibold tracking-[-0.035em]">
                Overview
              </h1>

              <p className="mt-2 text-[13px] text-neutral-500">
                Build, test, and operate your realtime AI agents.
              </p>
            </div>

            <section className="mt-8">
              <div className="grid grid-cols-3 border-y border-neutral-200">
                <div className="py-5 pr-6">
                  <p className="text-[11px] text-neutral-400">Agents</p>
                  <p className="mt-2 text-[20px] font-medium tracking-tight">
                    —
                  </p>
                </div>

                <div className="border-l border-neutral-200 px-6 py-5">
                  <p className="text-[11px] text-neutral-400">
                    Active sessions
                  </p>
                  <p className="mt-2 text-[20px] font-medium tracking-tight">
                    —
                  </p>
                </div>

                <div className="border-l border-neutral-200 px-6 py-5">
                  <p className="text-[11px] text-neutral-400">Usage</p>
                  <p className="mt-2 text-[20px] font-medium tracking-tight">
                    —
                  </p>
                </div>
              </div>
            </section>

            <section className="mt-12">
              <div className="flex items-end justify-between border-b border-neutral-200 pb-3">
                <div>
                  <h2 className="text-[13px] font-medium">Get started</h2>
                  <p className="mt-1 text-[11px] text-neutral-500">
                    Create your first realtime voice agent.
                  </p>
                </div>
              </div>

              <Link
                href="/agents/new"
                className="group flex items-center justify-between border-b border-neutral-200 py-5 transition-colors hover:bg-neutral-50"
              >
                <div className="flex items-center gap-4">
                  <div className="flex h-9 w-9 items-center justify-center rounded-md border border-neutral-200">
                    <Sparkles
                      className="h-4 w-4 text-neutral-700"
                      strokeWidth={1.7}
                    />
                  </div>

                  <div>
                    <p className="text-[12px] font-medium">
                      Create your first agent
                    </p>

                    <p className="mt-1 text-[11px] text-neutral-500">
                      Configure behavior, voice, and AI providers.
                    </p>
                  </div>
                </div>

                <span className="pr-1 text-[13px] text-neutral-400 transition-colors group-hover:text-neutral-800">
                  →
                </span>
              </Link>
            </section>
          </div>
        </main>
      </div>
    </div>
  );
}

