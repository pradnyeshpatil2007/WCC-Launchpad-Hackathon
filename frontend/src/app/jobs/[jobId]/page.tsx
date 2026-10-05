"use client";

import React, { useEffect, useState, use } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  XCircle,
  RotateCcw,
  Sparkles,
  CheckCircle2,
  Clock,
  AlertTriangle,
  Play,
  Film,
  Download,
} from "lucide-react";
import { api } from "@/lib/api";
import { useJobStore } from "@/lib/store";
import { ResilientSSEClient } from "@/lib/sse";
import { PipelineGraph } from "@/components/pipeline-graph/PipelineGraph";
import { ActivityFeed } from "@/components/activity-feed/ActivityFeed";
import { SceneStrip } from "@/components/scene-strip/SceneStrip";
import { VideoPlayer } from "@/components/video-player/VideoPlayer";

export default function JobPage({ params }: { params: Promise<{ jobId: string }> }) {
  const router = useRouter();
  const { jobId } = use(params);

  const runState = useJobStore((state) => state.runState);
  const setSnapshot = useJobStore((state) => state.setSnapshot);
  const applyEvent = useJobStore((state) => state.applyEvent);
  const setConnected = useJobStore((state) => state.setConnected);
  const selectedSceneIndex = useJobStore((state) => state.selectedSceneIndex);
  const setSelectedScene = useJobStore((state) => state.setSelectedScene);

  const [isCancelling, setIsCancelling] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"graph" | "player">("graph");

  // Rehydrate on initial load & establish SSE connection
  useEffect(() => {
    let sseClient: ResilientSSEClient | null = null;

    async function init() {
      try {
        // Fetch current snapshot from REST API to hydrate immediately
        const snapshot = await api.getJob(jobId);
        setSnapshot(snapshot);

        if (snapshot.status === "completed") {
          setActiveTab("player");
        }
      } catch (err: any) {
        if (!runState) {
          setLoadError(err.message || "Failed to load job.");
        }
      }

      // Open SSE stream
      sseClient = new ResilientSSEClient({
        jobId,
        initialLastEventId: runState?.lastEventId || 0,
        onEvent: (eventType, data, eventId) => {
          applyEvent(eventType, data, eventId);
          if (eventType === "job.completed") {
            setActiveTab("player");
          }
        },
        onConnected: () => setConnected(true),
        onError: () => setConnected(false),
      });

      sseClient.connect();
    }

    init();

    return () => {
      if (sseClient) {
        sseClient.disconnect();
      }
      setConnected(false);
    };
  }, [jobId]);

  const handleCancel = async () => {
    if (confirm("Are you sure you want to cancel this video generation?")) {
      setIsCancelling(true);
      try {
        await api.cancelJob(jobId);
      } catch (err) {
        console.error("Cancel failed:", err);
      } finally {
        setIsCancelling(false);
      }
    }
  };

  if (loadError && !runState) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-6 text-center">
        <AlertTriangle className="w-10 h-10 text-[#EF4444] mb-3" />
        <h2 className="text-lg font-bold text-white mb-2">Job Not Found</h2>
        <p className="text-xs text-[#9CA3AF] max-w-sm mb-6">{loadError}</p>
        <Link
          href="/"
          className="px-4 py-2 rounded-xl bg-[#FED766] text-black text-xs font-semibold"
        >
          Create New Video
        </Link>
      </div>
    );
  }

  const isRunning = runState?.status === "running" || runState?.status === "queued";
  const isCompleted = runState?.status === "completed";
  const isFailed = runState?.status === "failed";
  const progressPercent = Math.round((runState?.progress || 0) * 100);

  const selectedSceneStartTime =
    selectedSceneIndex !== null && runState?.sceneStartTimes
      ? runState.sceneStartTimes[selectedSceneIndex]
      : undefined;

  return (
    <div className="flex-1 flex flex-col p-4 md:p-6 max-w-7xl mx-auto w-full space-y-4">
      {/* Top Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 rounded-2xl glass-panel border border-white/5">
        <div className="flex items-center gap-3">
          <Link
            href="/"
            className="w-8 h-8 rounded-lg bg-white/5 hover:bg-white/10 flex items-center justify-center text-[#9CA3AF] hover:text-white transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
          </Link>

          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-bold text-white tracking-tight line-clamp-1">
                {runState?.title || runState?.prompt || "Video Generation"}
              </h2>

              {/* Status Pill */}
              <span
                className={`text-[10px] font-semibold px-2 py-0.5 rounded-full uppercase tracking-wider ${
                  isRunning
                    ? "bg-[#FED766]/15 text-[#FED766] border border-[#FED766]/30"
                    : isCompleted
                    ? "bg-[#10B981]/15 text-[#10B981] border border-[#10B981]/30"
                    : isFailed
                    ? "bg-[#EF4444]/15 text-[#EF4444] border border-[#EF4444]/30"
                    : "bg-[#6B7280]/20 text-[#9CA3AF]"
                }`}
              >
                {runState?.status || "queued"}
              </span>
            </div>

            <p className="text-[11px] text-[#9CA3AF] font-mono mt-0.5">
              ID: {jobId}
            </p>
          </div>
        </div>

        {/* Action Buttons & Tabs */}
        <div className="flex items-center gap-2">
          {isCompleted ? (
            <div className="flex rounded-xl bg-black/40 p-1 border border-white/10 shadow-inner">
              <button
                onClick={() => setActiveTab("player")}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all duration-200 ${
                  activeTab === "player"
                    ? "bg-[#FED766] text-black shadow-md scale-100"
                    : "text-[#9CA3AF] hover:text-white"
                }`}
              >
                <Play className="w-3.5 h-3.5 fill-current" />
                <span>Watch Short</span>
              </button>
              <button
                onClick={() => setActiveTab("graph")}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all duration-200 ${
                  activeTab === "graph"
                    ? "bg-[#FED766] text-black shadow-md scale-100"
                    : "text-[#9CA3AF] hover:text-white"
                }`}
              >
                <Film className="w-3.5 h-3.5" />
                <span>Pipeline Graph</span>
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-white/5 border border-white/10 text-xs text-[#9CA3AF]">
              <Clock className="w-3.5 h-3.5 text-[#FED766] animate-spin" />
              <span className="hidden sm:inline">Generating video (player unlocks on completion)</span>
              <span className="sm:hidden">Generating...</span>
            </div>
          )}

          {isRunning && (
            <button
              onClick={handleCancel}
              disabled={isCancelling}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-[#EF4444]/30 text-[#EF4444] hover:bg-[#EF4444]/10 transition-colors text-xs font-semibold disabled:opacity-50"
            >
              <XCircle className="w-4 h-4" />
              <span>{isCancelling ? "Cancelling..." : "Cancel"}</span>
            </button>
          )}
        </div>
      </div>

      {/* Live Overall Progress Bar */}
      <div className="w-full rounded-2xl glass-panel p-4 border border-white/5 space-y-2">
        <div className="flex items-center justify-between text-xs">
          <div className="flex items-center gap-2 font-medium">
            <span className="text-[#9CA3AF]">Overall Pipeline Progress</span>
            {isRunning && (
              <span className="flex items-center gap-1.5 text-[11px] text-[#FED766] font-normal">
                <span className="w-2 h-2 rounded-full bg-[#FED766] animate-pulse" />
                <span className="line-clamp-1">
                  {runState?.currentStage === "research"
                    ? "Drafting pedagogical script & scenes..."
                    : runState?.currentStage === "asset"
                    ? "Synthesizing voice narration & acquiring 9:16 visuals..."
                    : runState?.currentStage === "assembly"
                    ? "Rendering 1080x1920 video with smooth transitions & captions..."
                    : "Processing pipeline..."}
                </span>
              </span>
            )}
            {isCompleted && (
              <span className="text-[11px] text-[#10B981] font-normal flex items-center gap-1">
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>Video generation complete</span>
              </span>
            )}
          </div>
          <span className="font-mono text-white font-bold text-sm">{progressPercent}%</span>
        </div>
        <div className="w-full h-2.5 rounded-full bg-[#0E1015] overflow-hidden p-0.5 border border-white/5">
          <div
            className={`h-full transition-all duration-300 ease-out rounded-full ${
              isRunning
                ? "bg-gradient-to-r from-[#F59E0B] via-[#FED766] to-[#FDE047] progress-animated shadow-[0_0_12px_rgba(254,215,102,0.4)]"
                : isCompleted
                ? "bg-[#10B981] shadow-[0_0_10px_rgba(16,185,129,0.4)]"
                : "bg-[#EF4444]"
            }`}
            style={{ width: `${Math.max(2, progressPercent)}%` }}
          />
        </div>
      </div>

      {/* Failure Banner */}
      {isFailed && runState?.error && (
        <div className="p-4 rounded-xl bg-[#251517] border border-[#EF4444]/30 text-white flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-[#EF4444] shrink-0 mt-0.5" />
          <div className="flex-1">
            <h4 className="text-sm font-semibold text-[#EF4444]">Pipeline Execution Failed</h4>
            <p className="text-xs text-[#D1D5DB] mt-1">{runState.error.message}</p>
            <div className="mt-2 text-[11px] text-[#9CA3AF] font-mono">
              Stage: {runState.error.stage} • Code: {runState.error.code}
            </div>
          </div>
        </div>
      )}

      {/* Main Content: Player View or Pipeline Graph View */}
      {isCompleted && activeTab === "player" ? (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* Left Column: Vertical Video Player */}
          <div className="lg:col-span-5 flex justify-center">
            <VideoPlayer
              jobId={jobId}
              title={runState?.title}
              durationSec={runState?.durationSec || 60}
              sceneStartTimes={runState?.sceneStartTimes}
              seekTime={selectedSceneStartTime}
            />
          </div>

          {/* Right Column: Storyboard and Activity */}
          <div className="lg:col-span-7 space-y-4">
            <SceneStrip
              scenes={runState?.scenes || []}
              selectedSceneIndex={selectedSceneIndex}
              onSelectScene={(idx) => setSelectedScene(idx)}
              sceneStartTimes={runState?.sceneStartTimes}
              isCompleted={true}
            />

            <div className="h-[340px]">
              <ActivityFeed
                messages={runState?.activityFeed || []}
                connected={runState?.connected || false}
              />
            </div>
          </div>
        </div>
      ) : (
        /* Graph View: Live React Flow Pipeline + Feed */
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-start">
          <div className="lg:col-span-8 flex flex-col space-y-4">
            {runState && <PipelineGraph runState={runState} />}
            <SceneStrip
              scenes={runState?.scenes || []}
              selectedSceneIndex={selectedSceneIndex}
              onSelectScene={(idx) => setSelectedScene(idx)}
              sceneStartTimes={runState?.sceneStartTimes}
              isCompleted={false}
            />
          </div>

          <div className="lg:col-span-4 h-[720px]">
            <ActivityFeed
              messages={runState?.activityFeed || []}
              connected={runState?.connected || false}
            />
          </div>
        </div>
      )}
    </div>
  );
}
