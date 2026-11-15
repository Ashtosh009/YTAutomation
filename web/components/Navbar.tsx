"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import {
  Play,
  Film,
  ListOrdered,
  Lightbulb,
  Activity,
  LogOut,
  Menu,
  X,
  ExternalLink,
  ShieldCheck,
  Info,
} from "lucide-react";
import WorkflowRunsModal from "./WorkflowRunsModal";

export default function Navbar() {
  const pathname = usePathname();
  const router = useRouter();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [runsModalOpen, setRunsModalOpen] = useState(false);
  const [triggering, setTriggering] = useState<string | null>(null);

  // Hide Navbar completely on public login/about/privacy if desired, or show simplified navbar
  const isLoginPage = pathname === "/login";

  async function handleLogout() {
    try {
      await fetch("/api/auth/logout", { method: "POST" });
      router.push("/login");
      router.refresh();
    } catch (e) {
      console.error("Logout failed", e);
    }
  }

  async function triggerWorkflow(workflow: "generate.yml" | "upload.yml") {
    const label = workflow === "generate.yml" ? "Generate 9 Videos" : "Publish Daily 3";
    if (!confirm(`Trigger GitHub Actions workflow: '${label}'?`)) return;

    setTriggering(workflow);
    try {
      const res = await fetch("/api/github/trigger", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ workflow, count: 9 }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Failed to trigger workflow");
      alert(data.message || `Dispatched ${workflow}!`);
      setRunsModalOpen(true);
    } catch (err: any) {
      alert(`Trigger Error: ${err.message}`);
    } finally {
      setTriggering(null);
    }
  }

  if (isLoginPage) return null;

  const navLinks = [
    { href: "/", label: "Review Queue", icon: Film },
    { href: "/queue", label: "All Videos", icon: ListOrdered },
    { href: "/ideas", label: "Ideas Bank", icon: Lightbulb },
  ];

  return (
    <>
      <header className="sticky top-0 z-40 bg-channel-dark/95 backdrop-blur-md border-b border-channel-border">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            {/* Logo */}
            <div className="flex items-center gap-3">
              <Link href="/" className="flex items-center gap-2 group">
                <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-channel-purple to-channel-yellow flex items-center justify-center shadow-lg group-hover:scale-105 transition-transform">
                  <Play className="w-5 h-5 text-channel-darkest fill-channel-darkest ml-0.5" />
                </div>
                <div>
                  <span className="font-extrabold text-lg tracking-tight text-white group-hover:text-channel-accent transition-colors">
                    No Brain Stickman
                  </span>
                  <span className="hidden sm:inline-block ml-2 text-xs font-semibold px-2 py-0.5 rounded-full bg-channel-surface text-channel-accent border border-channel-border">
                    Studio
                  </span>
                </div>
              </Link>
            </div>

            {/* Desktop Nav */}
            <nav className="hidden md:flex items-center gap-1">
              {navLinks.map((item) => {
                const Icon = item.icon;
                const active = pathname === item.href;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-sm font-semibold transition-all ${
                      active
                        ? "bg-channel-surface text-channel-accent border border-channel-border shadow-inner"
                        : "text-slate-400 hover:text-white hover:bg-channel-surface/60"
                    }`}
                  >
                    <Icon className="w-4 h-4" />
                    <span>{item.label}</span>
                  </Link>
                );
              })}

              <button
                onClick={() => setRunsModalOpen(true)}
                className="flex items-center gap-2 px-3.5 py-2 rounded-lg text-sm font-semibold text-slate-400 hover:text-white hover:bg-channel-surface/60 transition-all"
                title="View GitHub Action Runs"
              >
                <Activity className="w-4 h-4 text-emerald-400" />
                <span>Runs</span>
              </button>
            </nav>

            {/* Action Buttons & Logout */}
            <div className="hidden md:flex items-center gap-3">
              <button
                onClick={() => triggerWorkflow("generate.yml")}
                disabled={triggering !== null}
                className="px-3.5 py-1.5 rounded-lg text-xs font-bold bg-channel-surface hover:bg-channel-border text-channel-accent border border-channel-border hover:border-channel-accent transition-all active:scale-95 disabled:opacity-50"
              >
                {triggering === "generate.yml" ? "Dispatching..." : "⚡ 9-Batch"}
              </button>

              <button
                onClick={() => triggerWorkflow("upload.yml")}
                disabled={triggering !== null}
                className="px-3.5 py-1.5 rounded-lg text-xs font-bold bg-channel-purple hover:bg-channel-purpleHover text-white shadow-md transition-all active:scale-95 disabled:opacity-50"
              >
                {triggering === "upload.yml" ? "Dispatching..." : "🚀 Daily 3"}
              </button>

              <button
                onClick={handleLogout}
                className="p-2 text-slate-400 hover:text-red-400 hover:bg-red-950/40 rounded-lg transition-colors border border-transparent hover:border-red-900/50"
                title="Logout"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>

            {/* Mobile menu button */}
            <div className="flex md:hidden items-center gap-2">
              <button
                onClick={() => setRunsModalOpen(true)}
                className="p-2 text-slate-400 hover:text-white"
                title="View Runs"
              >
                <Activity className="w-5 h-5 text-emerald-400" />
              </button>
              <button
                onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-channel-surface transition-colors"
              >
                {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
              </button>
            </div>
          </div>
        </div>

        {/* Mobile Dropdown */}
        {mobileMenuOpen && (
          <div className="md:hidden border-t border-channel-border bg-channel-dark/95 backdrop-blur-md px-4 pt-3 pb-5 space-y-2">
            {navLinks.map((item) => {
              const Icon = item.icon;
              const active = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setMobileMenuOpen(false)}
                  className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-semibold ${
                    active
                      ? "bg-channel-surface text-channel-accent border border-channel-border"
                      : "text-slate-300 hover:bg-channel-surface/60"
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  <span>{item.label}</span>
                </Link>
              );
            })}

            <div className="pt-3 border-t border-channel-border flex flex-col gap-2">
              <button
                onClick={() => {
                  setMobileMenuOpen(false);
                  triggerWorkflow("generate.yml");
                }}
                className="w-full py-2.5 rounded-lg text-xs font-bold bg-channel-surface text-channel-accent border border-channel-border text-center"
              >
                ⚡ Trigger 9-Batch (GitHub Actions)
              </button>
              <button
                onClick={() => {
                  setMobileMenuOpen(false);
                  triggerWorkflow("upload.yml");
                }}
                className="w-full py-2.5 rounded-lg text-xs font-bold bg-channel-purple text-white text-center"
              >
                🚀 Trigger Daily Upload (3 Videos)
              </button>
              <div className="flex items-center justify-between pt-2">
                <div className="flex gap-4 text-xs text-slate-400">
                  <Link href="/about" className="hover:text-white">About</Link>
                  <Link href="/privacy" className="hover:text-white">Privacy</Link>
                </div>
                <button
                  onClick={handleLogout}
                  className="flex items-center gap-1.5 text-xs text-red-400 hover:text-red-300 font-semibold"
                >
                  <LogOut className="w-3.5 h-3.5" />
                  <span>Logout</span>
                </button>
              </div>
            </div>
          </div>
        )}
      </header>

      {/* GitHub Workflow Runs Modal */}
      <WorkflowRunsModal
        isOpen={runsModalOpen}
        onClose={() => setRunsModalOpen(false)}
      />
    </>
  );
}
