/**
 * Canonical frontend types for AutoShorts matching Doc 2 §6-§9 and Doc 3 §14-§15.
 */

export type JobStatus =
  | "queued"
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

export type StageName =
  | "research"
  | "asset"
  | "assembly"
  | "complete"
  | "failed";

export type StageStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "skipped";

export interface StageInfo {
  stage: StageName;
  status: StageStatus;
  attempts: number;
  startedAt?: string | null;
  endedAt?: string | null;
  outputRef?: string | null;
  errorCode?: string | null;
}

export interface SceneData {
  sceneIndex: number;
  scriptText?: string;
  audioDurationSec?: number;
  visualSource?: "generated" | "stock";
  imageCount?: number;
  previewUrl?: string | null;
}

export interface ActivityMessage {
  id: string;
  timestamp: number;
  stage: string;
  message: string;
  type: "info" | "progress" | "success" | "warning" | "error";
}

export interface JobError {
  stage: string;
  code: string;
  message: string;
  retryable: boolean;
}

export interface RunState {
  id: string;
  prompt: string;
  status: JobStatus;
  currentStage: StageName;
  progress: number; // 0.0 to 1.0
  title?: string | null;
  durationSec?: number | null;
  thumbnailUrl?: string | null;
  videoUrl?: string | null;
  sceneCount?: number | null;
  sceneStartTimes?: number[] | null;
  error?: JobError | null;
  lastEventId: number;
  stages: Record<StageName, StageInfo>;
  scenes: SceneData[];
  activityFeed: ActivityMessage[];
  connected: boolean;
}

export interface JobSummary {
  id: string;
  prompt: string;
  status: JobStatus;
  stage: string;
  progress: number;
  title?: string | null;
  durationSec?: number | null;
  thumbnailUrl?: string | null;
  videoUrl?: string | null;
  createdAt?: string | null;
  completedAt?: string | null;
}
