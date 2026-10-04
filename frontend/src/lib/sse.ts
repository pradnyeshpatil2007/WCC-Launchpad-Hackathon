/**
 * Resilient Server-Sent Events (SSE) client matching Doc 2 §9.3.
 * Supports auto Last-Event-ID resume, exponential backoff (1s -> 30s) with jitter, and heartbeat handling.
 */

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

const EVENT_NAMES = [
  "job.snapshot",
  "stage.started",
  "stage.progress",
  "stage.completed",
  "substep.started",
  "substep.progress",
  "substep.completed",
  "script.ready",
  "scene.voice_ready",
  "scene.visual_ready",
  "retry.attempt",
  "fallback.used",
  "job.completed",
  "job.failed",
  "job.cancelled",
];

export interface SSEClientOptions {
  jobId: string;
  initialLastEventId?: number;
  onEvent: (eventType: string, data: any, eventId: number) => void;
  onConnected?: () => void;
  onError?: (err: any) => void;
}

export class ResilientSSEClient {
  private jobId: string;
  private lastEventId: number;
  private onEvent: (eventType: string, data: any, eventId: number) => void;
  private onConnected?: () => void;
  private onError?: (err: any) => void;

  private eventSource: EventSource | null = null;
  private isClosed: boolean = false;
  private reconnectAttempt: number = 0;
  private reconnectTimer: any = null;

  constructor(options: SSEClientOptions) {
    this.jobId = options.jobId;
    this.lastEventId = options.initialLastEventId || 0;
    this.onEvent = options.onEvent;
    this.onConnected = options.onConnected;
    this.onError = options.onError;
  }

  public connect(): void {
    if (this.isClosed) return;

    // Clean up previous instance
    this.cleanup();

    const url = new URL(
      `${API_BASE}/api/jobs/${encodeURIComponent(this.jobId)}/events`
    );
    if (this.lastEventId > 0) {
      url.searchParams.set("lastEventId", String(this.lastEventId));
    }

    try {
      this.eventSource = new EventSource(url.toString());

      this.eventSource.onopen = () => {
        this.reconnectAttempt = 0;
        if (this.onConnected) this.onConnected();
      };

      // Register listener for each event type
      for (const evName of EVENT_NAMES) {
        this.eventSource.addEventListener(evName, (e: MessageEvent) => {
          try {
            const parsedData = JSON.parse(e.data);
            const idNum = e.lastEventId ? parseInt(e.lastEventId, 10) : 0;
            if (idNum > this.lastEventId) {
              this.lastEventId = idNum;
            }

            this.onEvent(evName, parsedData, this.lastEventId);

            // Terminal events terminate the connection cleanly
            if (
              evName === "job.completed" ||
              evName === "job.failed" ||
              evName === "job.cancelled"
            ) {
              this.disconnect();
            }
          } catch (err) {
            console.error(`Failed to parse SSE payload for ${evName}:`, err);
          }
        });
      }

      this.eventSource.onerror = (err) => {
        if (this.isClosed) return;
        if (this.onError) this.onError(err);
        this.eventSource?.close();
        this.scheduleReconnect();
      };
    } catch (err) {
      if (this.onError) this.onError(err);
      this.scheduleReconnect();
    }
  }

  private scheduleReconnect(): void {
    if (this.isClosed) return;

    // Exponential backoff: 1s, 2s, 4s, 8s, 16s, capped at 30s + jitter
    const baseDelay = Math.min(1000 * Math.pow(2, this.reconnectAttempt), 30000);
    const jitter = Math.random() * 500;
    const delay = baseDelay + jitter;
    this.reconnectAttempt++;

    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
    }

    this.reconnectTimer = setTimeout(() => {
      this.connect();
    }, delay);
  }

  private cleanup(): void {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  public disconnect(): void {
    this.isClosed = true;
    this.cleanup();
  }
}
