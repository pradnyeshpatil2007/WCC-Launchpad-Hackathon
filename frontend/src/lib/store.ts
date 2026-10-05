/**
 * Zustand client state store with pure event reducers matching Doc 2 §6-§7 & §9.2.
 */

import { create } from "zustand";
import {
  ActivityMessage,
  JobStatus,
  RunState,
  SceneData,
  StageInfo,
  StageName,
} from "./types";

interface JobStore {
  runState: RunState | null;
  selectedSceneIndex: number | null;
  videoCurrentTime: number;
  
  // Actions
  initJob: (id: string, prompt: string) => void;
  setSnapshot: (snapshot: Partial<RunState>) => void;
  applyEvent: (eventType: string, data: any, eventId: number) => void;
  setSelectedScene: (index: number | null) => void;
  setVideoCurrentTime: (time: number) => void;
  setConnected: (connected: boolean) => void;
  reset: () => void;
}

const defaultStages: Record<StageName, StageInfo> = {
  research: { stage: "research", status: "pending", attempts: 1 },
  asset: { stage: "asset", status: "pending", attempts: 1 },
  assembly: { stage: "assembly", status: "pending", attempts: 1 },
  complete: { stage: "complete", status: "pending", attempts: 1 },
  failed: { stage: "failed", status: "pending", attempts: 0 },
};

function createInitialRunState(id: string, prompt: string): RunState {
  return {
    id,
    prompt,
    status: "queued",
    currentStage: "research",
    progress: 0.0,
    title: null,
    durationSec: null,
    thumbnailUrl: null,
    videoUrl: null,
    sceneCount: null,
    sceneStartTimes: null,
    error: null,
    lastEventId: 0,
    stages: { ...defaultStages },
    scenes: [],
    activityFeed: [
      {
        id: `init-${Date.now()}`,
        timestamp: Date.now(),
        stage: "system",
        message: "Job submitted. Connecting to live pipeline...",
        type: "info",
      },
    ],
    connected: false,
  };
}

export const useJobStore = create<JobStore>((set) => ({
  runState: null,
  selectedSceneIndex: null,
  videoCurrentTime: 0,

  initJob: (id: string, prompt: string) =>
    set({
      runState: createInitialRunState(id, prompt),
      selectedSceneIndex: null,
      videoCurrentTime: 0,
    }),

  setSnapshot: (snapshot: Partial<RunState>) =>
    set((state) => {
      if (!state.runState && snapshot.id) {
        state.runState = createInitialRunState(snapshot.id, snapshot.prompt || "");
      }
      if (!state.runState) return state;

      const current = state.runState;
      const updated: RunState = {
        ...current,
        ...snapshot,
        stages: {
          ...current.stages,
          ...(snapshot.stages || {}),
        },
        scenes: snapshot.scenes || current.scenes,
        activityFeed: snapshot.activityFeed || current.activityFeed,
      };
      return { runState: updated };
    }),

  setConnected: (connected: boolean) =>
    set((state) => {
      if (!state.runState) return state;
      return { runState: { ...state.runState, connected } };
    }),

  setSelectedScene: (index: number | null) => set({ selectedSceneIndex: index }),
  setVideoCurrentTime: (time: number) => set({ videoCurrentTime: time }),

  reset: () =>
    set({
      runState: null,
      selectedSceneIndex: null,
      videoCurrentTime: 0,
    }),

  applyEvent: (eventType: string, data: any, eventId: number) =>
    set((state) => {
      if (!state.runState) return state;
      const rs = { ...state.runState };
      rs.lastEventId = Math.max(rs.lastEventId, eventId);

      const addFeedMessage = (
        stage: string,
        message: string,
        type: ActivityMessage["type"] = "info"
      ) => {
        let finalType = type;
        if (type === "info" || type === "progress") {
          const lower = message.toLowerCase();
          if (
            lower.includes("completed") ||
            lower.includes("ready") ||
            lower.includes("acquired") ||
            lower.includes("validated") ||
            lower.includes("success") ||
            lower.includes("finished") ||
            lower.includes("drafted")
          ) {
            finalType = "success";
          }
        }
        const msg: ActivityMessage = {
          id: `ev-${eventId}-${Date.now()}`,
          timestamp: Date.now(),
          stage,
          message,
          type: finalType,
        };
        rs.activityFeed = [msg, ...rs.activityFeed].slice(0, 100);
      };

      switch (eventType) {
        case "job.snapshot": {
          rs.status = data.status || rs.status;
          rs.currentStage = data.stage || rs.currentStage;
          rs.progress = data.progress !== undefined ? data.progress : rs.progress;
          rs.title = data.title !== undefined ? data.title : rs.title;
          rs.durationSec = data.durationSec !== undefined ? data.durationSec : rs.durationSec;
          rs.thumbnailUrl = data.thumbnailUrl !== undefined ? data.thumbnailUrl : rs.thumbnailUrl;
          rs.videoUrl = data.videoUrl !== undefined ? data.videoUrl : rs.videoUrl;
          rs.error = data.error !== undefined ? data.error : rs.error;
          if (data.stages) {
            data.stages.forEach((s: any) => {
              const stageKey = s.stage as StageName;
              if (rs.stages[stageKey]) {
                rs.stages[stageKey] = {
                  ...rs.stages[stageKey],
                  status: s.status,
                  attempts: s.attempts || rs.stages[stageKey].attempts,
                };
              }
            });
          }
          break;
        }

        case "stage.started": {
          const st = data.stage as StageName;
          rs.status = "running";
          rs.currentStage = st;
          if (rs.stages[st]) {
            rs.stages[st] = {
              ...rs.stages[st],
              status: "running",
              startedAt: new Date().toISOString(),
            };
          }
          if (st === "research") rs.progress = Math.max(rs.progress, 0.08);
          if (st === "asset") rs.progress = Math.max(rs.progress, 0.35);
          if (st === "assembly") rs.progress = Math.max(rs.progress, 0.70);
          addFeedMessage(st, data.message || `Started ${st} stage`, "info");
          break;
        }

        case "stage.progress": {
          const st = data.stage as StageName;
          if (data.progress !== undefined) {
            rs.progress = Math.max(rs.progress, data.progress);
          }
          if (data.message) {
            addFeedMessage(st, data.message, "progress");
          }
          break;
        }

        case "stage.completed": {
          const st = data.stage as StageName;
          if (rs.stages[st]) {
            rs.stages[st] = {
              ...rs.stages[st],
              status: "completed",
              endedAt: new Date().toISOString(),
            };
          }
          if (st === "research") rs.progress = Math.max(rs.progress, 0.32);
          if (st === "asset") rs.progress = Math.max(rs.progress, 0.70);
          if (st === "assembly") rs.progress = Math.max(rs.progress, 0.99);
          addFeedMessage(st, data.message || `Completed ${st} stage`, "success");
          break;
        }

        case "substep.started": {
          addFeedMessage(data.node || rs.currentStage, data.message, "info");
          break;
        }

        case "substep.progress": {
          if (data.percent !== undefined && (data.node === "assembly" || rs.currentStage === "assembly")) {
            // Map assembly frame rendering percent (0-100) across 70% -> 98%
            const renderRatio = Math.max(0, Math.min(100, Number(data.percent))) / 100.0;
            rs.progress = Math.max(rs.progress, 0.70 + renderRatio * 0.28);
          }
          if (data.message) {
            addFeedMessage(data.node || rs.currentStage, data.message, "progress");
          }
          break;
        }

        case "substep.completed": {
          if (data.message) {
            addFeedMessage(data.node || rs.currentStage, data.message, "success");
          }
          break;
        }

        case "script.ready": {
          rs.title = data.title;
          rs.sceneCount = data.sceneCount;
          rs.progress = Math.max(rs.progress, 0.25);
          // Pre-populate scene slots
          const newScenes: SceneData[] = [];
          for (let i = 0; i < data.sceneCount; i++) {
            newScenes.push({
              sceneIndex: i,
            });
          }
          rs.scenes = newScenes;
          addFeedMessage(
            "research",
            `Script ready: "${data.title}" (${data.wordCount} words, ${data.sceneCount} scenes)`,
            "success"
          );
          break;
        }

        case "scene.voice_ready": {
          const idx = data.sceneIndex;
          rs.scenes = rs.scenes.map((sc) =>
            sc.sceneIndex === idx
              ? { ...sc, audioDurationSec: data.durationSec }
              : sc
          );
          const totalScenes = rs.sceneCount || rs.scenes.length || 6;
          const voiceReadyCount = rs.scenes.filter((s) => s.audioDurationSec !== undefined).length;
          rs.progress = Math.max(rs.progress, 0.35 + (voiceReadyCount / totalScenes) * 0.15);
          addFeedMessage(
            "voice",
            `Scene ${idx + 1} voice narration ready (${data.durationSec.toFixed(1)}s)`,
            "success"
          );
          break;
        }

        case "scene.visual_ready": {
          const idx = data.sceneIndex;
          rs.scenes = rs.scenes.map((sc) =>
            sc.sceneIndex === idx
              ? {
                  ...sc,
                  visualSource: data.source,
                  imageCount: data.imageCount,
                  previewUrl: data.previewUrl,
                }
              : sc
          );
          const totalScenes = rs.sceneCount || rs.scenes.length || 6;
          const visualsReadyCount = rs.scenes.filter((s) => s.previewUrl !== undefined).length;
          rs.progress = Math.max(rs.progress, 0.50 + (visualsReadyCount / totalScenes) * 0.20);
          addFeedMessage(
            "visuals",
            `Scene ${idx + 1} visual asset acquired (${data.source}, ${data.imageCount} image${data.imageCount > 1 ? "s" : ""})`,
            "success"
          );
          break;
        }

        case "retry.attempt": {
          addFeedMessage(
            data.node || rs.currentStage,
            `Attempt ${data.attempt}/${data.maxAttempts}: ${data.message}`,
            "warning"
          );
          break;
        }

        case "fallback.used": {
          addFeedMessage(
            data.node || rs.currentStage,
            `Fallback active: ${data.message}`,
            "warning"
          );
          break;
        }

        case "job.completed": {
          rs.status = "completed";
          rs.currentStage = "complete";
          rs.progress = 1.0;
          rs.videoUrl = data.videoUrl;
          rs.thumbnailUrl = data.thumbnailUrl;
          rs.durationSec = data.durationSec;
          rs.sceneStartTimes = data.sceneStartTimes;
          if (rs.stages.assembly) {
            rs.stages.assembly.status = "completed";
          }
          if (rs.stages.complete) {
            rs.stages.complete.status = "completed";
          }
          addFeedMessage("system", "Video generation finished successfully!", "success");
          break;
        }

        case "job.failed": {
          rs.status = "failed";
          rs.currentStage = "failed";
          rs.error = {
            stage: data.stage || "unknown",
            code: data.code || "INTERNAL_ERROR",
            message: data.message || "Job execution failed",
            retryable: data.retryable ?? false,
          };
          const errStage = data.stage as StageName;
          if (rs.stages[errStage]) {
            rs.stages[errStage].status = "failed";
            rs.stages[errStage].errorCode = data.code;
          }
          addFeedMessage(
            data.stage || "error",
            `Pipeline failed: ${data.message}`,
            "error"
          );
          break;
        }

        case "job.cancelled": {
          rs.status = "cancelled";
          addFeedMessage("system", "Job was cancelled by user.", "warning");
          break;
        }

        default:
          break;
      }

      return { runState: rs };
    }),
}));
