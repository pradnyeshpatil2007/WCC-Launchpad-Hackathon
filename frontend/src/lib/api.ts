/**
 * Type-safe REST client for AutoShorts backend matching Doc 2 §8 and Doc 3 §14.
 */

import { JobSummary, RunState } from "./types";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export class ApiError extends Error {
  code: string;
  retryable: boolean;
  status: number;

  constructor(status: number, code: string, message: string, retryable: boolean = false) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.retryable = retryable;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE}${path}`;
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };

  const resp = await fetch(url, { ...options, headers });

  if (!resp.ok) {
    let errCode = "HTTP_ERROR";
    let errMsg = `Request failed with HTTP ${resp.status}`;
    let retryable = resp.status >= 500 || resp.status === 429;

    try {
      const errJson = await resp.json();
      if (errJson?.error) {
        errCode = errJson.error.code || errCode;
        errMsg = errJson.error.message || errMsg;
        retryable = errJson.error.retryable ?? retryable;
      } else if (errJson?.detail) {
        if (typeof errJson.detail === "object" && errJson.detail.error) {
          errCode = errJson.detail.error.code || errCode;
          errMsg = errJson.detail.error.message || errMsg;
          retryable = errJson.detail.error.retryable ?? retryable;
        } else if (typeof errJson.detail === "string") {
          errMsg = errJson.detail;
        }
      }
    } catch {
      // Body not JSON
    }

    throw new ApiError(resp.status, errCode, errMsg, retryable);
  }

  if (resp.status === 204) {
    return {} as T;
  }

  return (await resp.json()) as T;
}

export const api = {
  /**
   * Health probe check
   */
  async getHealth(): Promise<{ status: string; version: string }> {
    return request<{ status: string; version: string }>("/health");
  },

  /**
   * Create a new video generation job
   */
  async createJob(prompt: string): Promise<{ id: string; status: string }> {
    return request<{ id: string; status: string }>("/api/jobs", {
      method: "POST",
      body: JSON.stringify({ prompt: prompt.trim() }),
    });
  },

  /**
   * Fetch current job state snapshot
   */
  async getJob(jobId: string): Promise<RunState> {
    return request<RunState>(`/api/jobs/${encodeURIComponent(jobId)}`);
  },

  /**
   * List historical and active jobs for Library view
   */
  async listJobs(status?: string, limit: number = 50): Promise<JobSummary[]> {
    const params = new URLSearchParams();
    if (status) params.set("status", status);
    params.set("limit", String(limit));
    const data = await request<{ jobs: JobSummary[] }>(`/api/jobs?${params.toString()}`);
    return data.jobs || [];
  },

  /**
   * Cancel an actively running job
   */
  async cancelJob(jobId: string): Promise<{ ok: boolean }> {
    return request<{ ok: boolean }>(`/api/jobs/${encodeURIComponent(jobId)}/cancel`, {
      method: "POST",
    });
  },

  /**
   * Delete a job, its DB records, and media
   */
  async deleteJob(jobId: string): Promise<void> {
    await request<void>(`/api/jobs/${encodeURIComponent(jobId)}`, {
      method: "DELETE",
    });
  },

  /**
   * Resolve media URLs
   */
  getVideoUrl(jobId: string): string {
    return `${API_BASE}/api/media/${encodeURIComponent(jobId)}/video.mp4`;
  },

  getThumbnailUrl(jobId: string): string {
    return `${API_BASE}/api/media/${encodeURIComponent(jobId)}/thumbnail.jpg`;
  },

  getScenePreviewUrl(jobId: string, sceneIndex: number): string {
    return `${API_BASE}/api/media/${encodeURIComponent(jobId)}/scenes/${sceneIndex}/preview`;
  },
};
