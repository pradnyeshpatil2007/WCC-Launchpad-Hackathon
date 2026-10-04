"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Film,
  PlusCircle,
  Clapperboard,
  Sparkles,
  Activity,
  CheckCircle2,
  Clock,
  AlertCircle,
  ChevronRight,
} from "lucide-react";
import { api } from "@/lib/api";
import { JobSummary } from "@/lib/types";

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [recentJobs, setRecentJobs] = useState<JobSummary[]>([]);
  const [apiOnline, setApiOnline] = useState<boolean>(true);

  useEffect(() => {
    async function loadStatus() {
      try {
        await api.getHealth();
        setApiOnline(true);
      } catch {
        setApiOnline(false);
      }

      try {
        const jobs = await api.listJobs(undefined, 5);
        setRecentJobs(jobs);
      } catch {
        // Handled silently
      }
    }

    loadStatus();
    const interval = setInterval(loadStatus, 15000);
    return () => clearInterval(interval);
  }, [pathname]);

  const getStatusDot = (status: string) => {
    switch (status) {
      case "completed":
        return <span className="w-2 h-2 rounded-full bg-[#10B981]" />;
      case "running":
        return <span className="w-2 h-2 rounded-full bg-[#FED766] animate-pulse" />;
      case "failed":
        return <span className="w-2 h-2 rounded-full bg-[#EF4444]" />;
      default:
        return <span className="w-2 h-2 rounded-full bg-[#6B7280]" />;
    }
  };

  return (
    <div className="flex h-screen w-full bg-[#0E1015] text-[#F3F4F6] overflow-hidden font-sans">
      {/* Sidebar */}
      <aside className="hidden md:flex flex-col w-64 border-r border-[#262B35] bg-[#12151D] p-4 justify-between shrink-0">
        <div className="space-y-6">
          {/* Logo */}
          <Link href="/" className="flex items-center gap-3 px-2 group">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-[#E07A5F] to-[#FED766] p-0.5 flex items-center justify-center shadow-lg group-hover:scale-105 transition-transform">
              <div className="w-full h-full bg-[#0E1015] rounded-[10px] flex items-center justify-center">
                <Film className="w-5 h-5 text-[#FED766]" />
              </div>
            </div>
            <div>
              <span className="font-bold text-base tracking-tight text-white flex items-center gap-1.5">
                AutoShorts
                <span className="text-[9px] px-1.5 py-0.5 rounded bg-[#FED766]/10 text-[#FED766] font-mono border border-[#FED766]/20">
                  AI
                </span>
              </span>
              <p className="text-[10px] text-[#9CA3AF] leading-none mt-0.5">
                Multi-Agent Video Pipeline
              </p>
            </div>
          </Link>

          {/* Primary Navigation */}
          <nav className="space-y-1">
            <Link
              href="/"
              className={`flex items-center justify-between px-3 py-2.5 rounded-xl text-sm font-medium transition-colors ${
                pathname === "/"
                  ? "bg-[#FED766] text-black font-semibold shadow-md"
                  : "text-[#D1D5DB] hover:bg-white/5 hover:text-white"
              }`}
            >
              <div className="flex items-center gap-2.5">
                <PlusCircle className={`w-4 h-4 ${pathname === "/" ? "text-black" : "text-[#FED766]"}`} />
                <span>New Video</span>
              </div>
              <ChevronRight className="w-3.5 h-3.5 opacity-60" />
            </Link>

            <Link
              href="/library"
              className={`flex items-center justify-between px-3 py-2.5 rounded-xl text-sm font-medium transition-colors ${
                pathname === "/library"
                  ? "bg-white/10 text-white"
                  : "text-[#9CA3AF] hover:bg-white/5 hover:text-white"
              }`}
            >
              <div className="flex items-center gap-2.5">
                <Clapperboard className="w-4 h-4 text-[#9CA3AF]" />
                <span>Library</span>
              </div>
              <ChevronRight className="w-3.5 h-3.5 opacity-60" />
            </Link>
          </nav>

          {/* Recent Creations */}
          <div className="space-y-2 pt-2 border-t border-white/5">
            <div className="px-2 flex items-center justify-between">
              <span className="text-[11px] font-semibold text-[#9CA3AF] uppercase tracking-wider">
                Recent
              </span>
              <Link href="/library" className="text-[10px] text-[#FED766] hover:underline">
                View all
              </Link>
            </div>

            <div className="space-y-1">
              {recentJobs.length === 0 ? (
                <p className="text-xs text-[#6B7280] px-2 py-1">No jobs yet</p>
              ) : (
                recentJobs.map((job) => (
                  <Link
                    key={job.id}
                    href={`/jobs/${job.id}`}
                    className={`flex items-center gap-2 px-2.5 py-2 rounded-lg text-xs transition-colors truncate ${
                      pathname === `/jobs/${job.id}`
                        ? "bg-white/10 text-white"
                        : "text-[#9CA3AF] hover:bg-white/5 hover:text-[#D1D5DB]"
                    }`}
                  >
                    {getStatusDot(job.status)}
                    <span className="truncate">{job.title || job.prompt}</span>
                  </Link>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Backend health footer */}
        <div className="pt-4 border-t border-white/5 flex items-center justify-between text-xs text-[#9CA3AF] px-2">
          <div className="flex items-center gap-2">
            <span
              className={`w-2 h-2 rounded-full ${
                apiOnline ? "bg-[#10B981]" : "bg-[#EF4444]"
              }`}
            />
            <span className="text-[11px]">
              {apiOnline ? "Backend Live" : "Offline"}
            </span>
          </div>
          <span className="text-[10px] font-mono opacity-50">v1.0.0</span>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col h-full overflow-y-auto bg-[#0E1015]">
        {children}
      </main>
    </div>
  );
}
