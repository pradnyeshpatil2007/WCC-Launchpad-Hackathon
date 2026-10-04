"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  Film,
  Play,
  Trash2,
  Clock,
  CheckCircle2,
  AlertCircle,
  Loader2,
  PlusCircle,
  ExternalLink,
} from "lucide-react";
import { api } from "@/lib/api";
import { JobSummary } from "@/lib/types";

export default function LibraryPage() {
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [filter, setFilter] = useState<string>("all");
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const fetchJobs = async () => {
    try {
      const data = await api.listJobs();
      setJobs(data);
    } catch (err) {
      console.error("Failed to load jobs:", err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchJobs();
    const interval = setInterval(fetchJobs, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleDelete = async (e: React.MouseEvent, jobId: string) => {
    e.preventDefault();
    e.stopPropagation();

    if (confirm("Delete this video project and all rendered files?")) {
      setDeletingId(jobId);
      try {
        await api.deleteJob(jobId);
        setJobs((prev) => prev.filter((j) => j.id !== jobId));
      } catch (err) {
        console.error("Failed to delete job:", err);
      } finally {
        setDeletingId(null);
      }
    }
  };

  const filteredJobs = jobs.filter((job) => {
    if (filter === "all") return true;
    if (filter === "completed") return job.status === "completed";
    if (filter === "running") return job.status === "running" || job.status === "queued";
    if (filter === "failed") return job.status === "failed";
    return true;
  });

  return (
    <div className="flex-1 flex flex-col p-6 md:p-10 max-w-7xl mx-auto w-full">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
        <div>
          <h1 className="text-2xl md:text-3xl font-extrabold text-white tracking-tight">
            Video Library
          </h1>
          <p className="text-xs md:text-sm text-[#9CA3AF] mt-1">
            Review and download your generated 60-second educational videos.
          </p>
        </div>

        <Link
          href="/"
          className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-[#FED766] text-black font-semibold text-xs md:text-sm hover:bg-[#FDE047] transition-all shadow-md self-start sm:self-auto"
        >
          <PlusCircle className="w-4 h-4" />
          <span>New Video</span>
        </Link>
      </div>

      {/* Filter Tabs */}
      <div className="flex items-center gap-2 mb-6 border-b border-white/5 pb-3">
        {["all", "completed", "running", "failed"].map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-3 py-1.5 rounded-xl text-xs font-medium capitalize transition-colors ${
              filter === f
                ? "bg-white/10 text-white border border-white/10"
                : "text-[#9CA3AF] hover:text-white"
            }`}
          >
            {f}
          </button>
        ))}
      </div>

      {/* Jobs Grid */}
      {isLoading ? (
        <div className="flex items-center justify-center p-16 text-[#9CA3AF]">
          <Loader2 className="w-6 h-6 animate-spin mr-2 text-[#FED766]" />
          <span className="text-sm">Loading creations...</span>
        </div>
      ) : filteredJobs.length === 0 ? (
        <div className="flex flex-col items-center justify-center p-16 text-center glass-panel rounded-2xl border border-white/5">
          <Film className="w-12 h-12 text-[#4B5563] mb-3" />
          <h3 className="text-sm font-semibold text-white mb-1">No videos found</h3>
          <p className="text-xs text-[#9CA3AF] max-w-sm mb-6">
            {filter === "all"
              ? "You haven't generated any educational videos yet."
              : `No videos matching filter "${filter}".`}
          </p>
          <Link
            href="/"
            className="px-4 py-2 rounded-xl bg-[#FED766] text-black text-xs font-semibold"
          >
            Create Your First Video
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
          {filteredJobs.map((job) => {
            const isDone = job.status === "completed";
            const isRun = job.status === "running" || job.status === "queued";
            const isFail = job.status === "failed";
            const thumbUrl = api.getThumbnailUrl(job.id);

            return (
              <Link
                key={job.id}
                href={`/jobs/${job.id}`}
                className="group flex flex-col rounded-2xl glass-panel border border-white/5 hover:border-white/20 transition-all duration-300 overflow-hidden shadow-lg"
              >
                {/* 9:16 Video Thumbnail Container */}
                <div className="w-full aspect-[9/16] bg-[#0E1015] relative overflow-hidden flex items-center justify-center">
                  {isDone ? (
                    <img
                      src={thumbUrl}
                      alt={job.title || job.prompt}
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                    />
                  ) : (
                    <div className="flex flex-col items-center gap-2 text-[#6B7280]">
                      {isRun ? (
                        <>
                          <Loader2 className="w-8 h-8 animate-spin text-[#FED766]" />
                          <span className="text-xs font-medium text-[#FED766]">
                            Generating ({Math.round(job.progress * 100)}%)
                          </span>
                        </>
                      ) : (
                        <>
                          <AlertCircle className="w-8 h-8 text-[#EF4444]" />
                          <span className="text-xs text-[#EF4444]">Failed</span>
                        </>
                      )}
                    </div>
                  )}

                  {/* Play icon overlay on hover for completed items */}
                  {isDone && (
                    <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                      <div className="w-12 h-12 rounded-full bg-[#FED766] text-black flex items-center justify-center shadow-lg transform group-hover:scale-110 transition-transform">
                        <Play className="w-6 h-6 fill-black translate-x-0.5" />
                      </div>
                    </div>
                  )}

                  {/* Duration Pill */}
                  {job.durationSec && (
                    <span className="absolute bottom-2 right-2 px-2 py-0.5 rounded-md text-[10px] font-mono bg-black/80 backdrop-blur-sm text-white">
                      {job.durationSec.toFixed(1)}s
                    </span>
                  )}

                  {/* Status Pill */}
                  <span
                    className={`absolute top-2 left-2 px-2 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider ${
                      isDone
                        ? "bg-[#10B981]/80 text-white"
                        : isRun
                        ? "bg-[#FED766]/90 text-black animate-pulse"
                        : "bg-[#EF4444]/80 text-white"
                    }`}
                  >
                    {job.status}
                  </span>
                </div>

                {/* Card Info */}
                <div className="p-4 flex flex-col justify-between flex-1 gap-3">
                  <div>
                    <h3 className="text-sm font-semibold text-white tracking-tight line-clamp-1 group-hover:text-[#FED766] transition-colors">
                      {job.title || job.prompt}
                    </h3>
                    <p className="text-xs text-[#9CA3AF] line-clamp-2 mt-1">
                      {job.prompt}
                    </p>
                  </div>

                  <div className="flex items-center justify-between pt-2 border-t border-white/5 text-[11px] text-[#6B7280]">
                    <span className="font-mono">
                      {job.createdAt ? new Date(job.createdAt).toLocaleDateString() : ""}
                    </span>

                    <button
                      onClick={(e) => handleDelete(e, job.id)}
                      disabled={deletingId === job.id}
                      className="p-1.5 rounded-lg text-[#6B7280] hover:text-[#EF4444] hover:bg-[#EF4444]/10 transition-colors"
                      title="Delete video"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
