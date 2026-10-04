"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { Sparkles, ArrowRight, Video, Zap, Compass, CheckCircle } from "lucide-react";
import { api } from "@/lib/api";
import { useJobStore } from "@/lib/store";

const EXAMPLE_TOPICS = [
  "Why do neutron stars spin so fast?",
  "How does cellular mitosis work?",
  "Why is the Mariana Trench so deep?",
  "What causes the Northern Lights?",
  "How do deep sea anglerfish survive?",
  "Why is copper used in electrical wiring?",
];

export default function HomePage() {
  const router = useRouter();
  const initJob = useJobStore((state) => state.initJob);

  const [prompt, setPrompt] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const cleanPrompt = prompt.trim();

    if (!cleanPrompt || cleanPrompt.length < 3) {
      setError("Please enter a topic with at least 3 characters.");
      return;
    }

    if (cleanPrompt.length > 500) {
      setError("Topic prompt must be 500 characters or fewer.");
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      const resp = await api.createJob(cleanPrompt);
      // Immediately initialize store and navigate to live job view (< 300ms perceived target)
      initJob(resp.id, cleanPrompt);
      router.push(`/jobs/${resp.id}`);
    } catch (err: any) {
      setIsSubmitting(false);
      setError(err.message || "Failed to launch pipeline. Please verify backend connection.");
    }
  };

  return (
    <div className="flex-1 flex flex-col items-center justify-center p-6 md:p-12 max-w-4xl mx-auto w-full">
      {/* Hero Badge */}
      <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-[#FED766]/10 border border-[#FED766]/20 text-[#FED766] text-xs font-medium mb-6">
        <Sparkles className="w-3.5 h-3.5" />
        <span>Agentic Multi-Agent Educational Video Generation</span>
      </div>

      {/* Main Title & Subtitle */}
      <h1 className="text-4xl md:text-5xl font-extrabold text-white text-center tracking-tight max-w-2xl leading-tight">
        Turn any educational concept into a{" "}
        <span className="text-transparent bg-clip-text bg-gradient-to-r from-[#E07A5F] via-[#FED766] to-[#FDE047]">
          60-second video
        </span>
      </h1>

      <p className="text-sm md:text-base text-[#9CA3AF] text-center max-w-xl mt-4 mb-8 leading-relaxed">
        Autonomous pipeline: Research script writing, Edge-TTS audio narration, smart vertical visual sourcing, and FFmpeg karaoke pop subtitles.
      </p>

      {/* Composer Input Box */}
      <form onSubmit={handleSubmit} className="w-full max-w-2xl relative mb-6">
        <div className="relative rounded-2xl glass-panel p-2 border border-white/10 shadow-2xl focus-within:border-[#FED766]/60 focus-within:ring-2 focus-within:ring-[#FED766]/20 transition-all">
          <textarea
            value={prompt}
            onChange={(e) => {
              setPrompt(e.target.value);
              if (error) setError(null);
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSubmit();
              }
            }}
            placeholder="What would you like to explain? (e.g. Why do stars produce light?)"
            rows={3}
            className="w-full bg-transparent text-white placeholder-[#6B7280] text-sm md:text-base p-3 resize-none focus:outline-none"
            disabled={isSubmitting}
          />

          <div className="flex items-center justify-between px-3 pt-2 pb-1 border-t border-white/5">
            <span className="text-[11px] text-[#6B7280]">
              {prompt.length}/500 chars
            </span>

            <button
              type="submit"
              disabled={isSubmitting || !prompt.trim()}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-[#FED766] text-black font-semibold text-xs md:text-sm hover:bg-[#FDE047] disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-md group"
            >
              <span>{isSubmitting ? "Launching..." : "Generate Video"}</span>
              <ArrowRight className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
            </button>
          </div>
        </div>

        {error && (
          <p className="text-xs text-[#EF4444] mt-2 px-3 font-medium">{error}</p>
        )}
      </form>

      {/* Example Prompts */}
      <div className="w-full max-w-2xl">
        <p className="text-xs font-semibold text-[#9CA3AF] uppercase tracking-wider mb-3 px-1">
          Or try an example topic:
        </p>

        <div className="flex flex-wrap gap-2">
          {EXAMPLE_TOPICS.map((topic, i) => (
            <button
              key={i}
              type="button"
              onClick={() => {
                setPrompt(topic);
                if (error) setError(null);
              }}
              className="px-3 py-1.5 rounded-xl glass-card text-xs text-[#D1D5DB] hover:text-white hover:border-[#FED766]/40 transition-all text-left"
            >
              {topic}
            </button>
          ))}
        </div>
      </div>

      {/* Pipeline Guarantees Badges */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 w-full max-w-2xl mt-12 pt-8 border-t border-white/5 text-xs text-[#9CA3AF]">
        <div className="flex items-center gap-2.5">
          <CheckCircle className="w-4 h-4 text-[#10B981]" />
          <span>Real live APIs (Zero mocks)</span>
        </div>
        <div className="flex items-center gap-2.5">
          <CheckCircle className="w-4 h-4 text-[#10B981]" />
          <span>Strict &lt;60s vertical format</span>
        </div>
        <div className="flex items-center gap-2.5">
          <CheckCircle className="w-4 h-4 text-[#10B981]" />
          <span>Live SSE node graph</span>
        </div>
      </div>
    </div>
  );
}
