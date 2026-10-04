# AutoShorts: Frontend Specification

**Document 2 of 3** | WCC Launchpad 30, Agentic AI Track
**Status:** Draft v1.0 for confirmation
**Depends on:** Document 1 (PRD). IDs such as `FR-40`, `GR-06`, `§9` refer to it.
**Feeds:** Document 3 (Backend & Architecture Spec), which MUST conform to the API and SSE contracts in §8 and §9.

---

## 1. Purpose & Principles

The frontend is a **thin, beautiful, honest window** onto a long-running backend process. It owns presentation, interaction, and live progress visualization. It owns **no** business logic about providers, prompts, keys, or media processing.

| # | Principle | Consequence |
|---|---|---|
| 1 | **Calm and content-first** | Warm neutrals, generous whitespace, one primary action per screen |
| 2 | **Never a dead wait** | Something meaningful changes on screen at least every few seconds while a job runs |
| 3 | **Zero secrets, zero raw payloads** | The browser only ever receives sanitized, allow-listed data (PRD FR-42, GR-06) |
| 4 | **Truth over theatre** | The node graph reflects real backend state. It is never a canned animation timed with `setTimeout` |
| 5 | **No fabricated data** | No fixtures, no placeholder library items, no fake progress (PRD §9) |
| 6 | **Resilient by construction** | Reconnects, resumes, and handles every error state with human language |

---

## 2. Technology Stack

| Concern | Choice | Notes |
|---|---|---|
| Framework | **Next.js 15 (App Router)**, React 19, **TypeScript (strict)** | `noUncheckedIndexedAccess` on |
| Styling | **Tailwind CSS v4** + CSS variables for design tokens | Tokens in §4 |
| Primitives | **Radix UI** (via shadcn/ui, copied in and restyled, not left default) | Dialog, DropdownMenu, Tooltip, Toast |
| Motion | **Motion** (formerly Framer Motion) | Respect `prefers-reduced-motion` |
| Node graph | **@xyflow/react (React Flow)**, custom node and edge components | Read-only, non-draggable, auto-laid-out (§7) |
| Client state | **Zustand** (with `immer`) | Live job state, UI prefs |
| Server state | **TanStack Query v5** | Library list, job detail, mutations |
| Validation | **Zod** | Validates every REST response and every SSE event at the boundary |
| SSE | Native **`EventSource`** wrapped in a resilient client | Auto `Last-Event-ID` resume (§9.3) |
| Icons | **lucide-react** | |
| Fonts | `next/font`: **Newsreader** (display serif), **Inter** (UI), **Geist Mono** (numerals/timers) | |
| Theming | `next-themes` | Light, dark, system |
| Testing | **Playwright** (real backend, real APIs), **Vitest** for pure logic only | See §16 |
| Lint/format | ESLint (strict), Prettier, `tsc --noEmit` in CI | |

**Rule:** No library may be added that ships mock servers (MSW, json-server, faker, etc.). Add a lint rule banning imports of `msw`, `@faker-js/*`, `faker`, `nock`.

---

## 3. Information Architecture & Routing

```
/                      Home: the prompt composer (empty-state hero)
/jobs/[jobId]          Job view: live generation screen → result screen → failure screen
/library               Library ("My Creations") grid
/not-found             Friendly 404
```

A single `/jobs/[jobId]` route handles **all** job states. The same URL goes from live graph to finished video without navigation, and is reload-safe and shareable on the local machine.

### 3.1 App shell
- **Left sidebar** (collapsible; becomes a bottom sheet / top bar on mobile):
  - Logo/wordmark "AutoShorts"
  - **New video** (primary)
  - **Library**
  - **Recent** (5 most recent jobs with status dots: running pulse, done check, failed warning)
  - Theme toggle (bottom)
- **Main column**: centered, `max-width: 720px` for the composer; wider canvas for the job view.

### 3.2 Navigation behavior
- Submitting a prompt navigates to `/jobs/[jobId]` **immediately** after `POST /api/jobs` returns (target < 300 ms perceived).
- Leaving a running job's page does **not** cancel it. Cancel is an explicit action.
- Opening a running job from Library reconnects the SSE stream and rehydrates the graph (§9.4).

---

## 4. Design System

Inspired by Claude's interface (warm paper tones, serif headlines, soft terracotta accent), with ChatGPT-like composer ergonomics and Gemini-like subtle gradients used **sparingly**.

### 4.1 Color tokens (CSS variables)

| Token | Light | Dark |
|---|---|---|
| `--bg` | `#FAF9F5` | `#1F1E1D` |
| `--bg-elevated` | `#FFFFFF` | `#262624` |
| `--bg-sunken` | `#F0EEE6` | `#191918` |
| `--border` | `#E6E3DA` | `#3A3936` |
| `--text` | `#1F1E1D` | `#ECEAE3` |
| `--text-muted` | `#6B685F` | `#A8A59B` |
| `--accent` | `#C96442` | `#D97757` |
| `--accent-soft` | `#F6E6DE` | `#3A2A24` |
| `--success` | `#3F7D58` | `#6BB88A` |
| `--warning` | `#B7791F` | `#E0A94B` |
| `--danger` | `#B3412F` | `#E07A68` |
| `--graph-edge` | `#CFCABD` | `#4A4843` |
| `--graph-active` | `var(--accent)` | `var(--accent)` |

All text/background pairs MUST meet **WCAG AA** (4.5:1 body, 3:1 large text).

### 4.2 Typography
| Role | Font | Size / Weight |
|---|---|---|
| Hero headline | Newsreader | 40-48px / 500, tight tracking |
| Page titles | Newsreader | 28px / 500 |
| Body & UI | Inter | 15-16px / 400-500 |
| Captions, status | Inter | 13px / 500, muted |
| Timers, counters | Geist Mono | 13px, tabular numerals |

### 4.3 Shape, spacing, elevation
- Radius: `8px` (controls), `14px` (cards), `22px` (composer), `9999px` (chips).
- Spacing scale: 4px base (4, 8, 12, 16, 24, 32, 48, 64).
- Elevation: borders first, shadows second (`0 1px 2px rgb(0 0 0 / 6%)`; composer focus adds a soft 3px accent ring at 25% opacity).

### 4.4 Motion tokens
| Token | Value | Use |
|---|---|---|
| `--ease-out` | `cubic-bezier(0.22, 1, 0.36, 1)` | Entrances |
| `--ease-in-out` | `cubic-bezier(0.65, 0, 0.35, 1)` | Transitions |
| `--dur-fast` | `120ms` | Hover/press |
| `--dur-base` | `240ms` | Panels, fades |
| `--dur-slow` | `600ms` | Graph state transitions |

`prefers-reduced-motion: reduce` → replace translations/scales with opacity fades, stop looping pulses, and freeze edge flow animation (state is still conveyed via color and text).

---

## 5. Screens

### 5.1 Home (`/`)
**Layout:** vertically centered column.
1. Greeting headline in serif (static, e.g., "What shall we explain today?").
2. **Composer**: auto-growing textarea (1-4 lines), 22px radius, placeholder "Describe a topic, e.g. *How do black holes form?*", character counter appears at 400+ of 500.
3. Primary **Create** button (accent, arrow icon). `Enter` submits; `Shift+Enter` newline.
4. Below: three **suggestion chips** (static copy. These are UI hints, not data; clicking fills the composer, never auto-submits).
5. Footer microcopy: "Videos take a few minutes. You can leave and come back."

**Validation (FR-01):** 3-500 chars, trimmed. Button disabled otherwise; inline helper text, no red flashes while typing.

**Submit states:** idle → submitting (button shows inline spinner, composer locked) → navigate. On network/API error: inline error banner under the composer with **Try again**, preserving the typed text.

### 5.2 Job View: Live Generation (`/jobs/[id]`, status `queued|running`)
Composition (desktop, ≥ 1024px):

```
┌───────────────────────────────────────────────────────────┐
│  Topic title (serif)                      [Cancel]  00:42 │
│  Live status line (aria-live): "Writing a 58-second script"│
├───────────────────────────────────────────────────────────┤
│                                                           │
│            NODE GRAPH CANVAS  (see §7)                    │
│                                                           │
├──────────────────────────────┬────────────────────────────┤
│  Scene strip (progress chips)│  Activity feed (humanized) │
└──────────────────────────────┴────────────────────────────┘
```

- **Header:** topic (the user's prompt, truncated to 2 lines) and, once Research completes, the generated **video title**. Elapsed timer in mono. **Cancel** is a quiet secondary action with a confirm dialog.
- **Status line:** a single sentence in plain language, the latest `message` from the stream, cross-faded on change. This is the `aria-live="polite"` region.
- **Node graph:** the hero (§7).
- **Scene strip:** one chip per scene (appears after Research completes). Each chip shows scene number and tiny state icons for *voice* and *visual*. When a scene's visual is ready, the chip expands into a **real thumbnail** of that scene's image (via the media route in §8.2, SHOULD). This produces the "video taking shape" effect.
- **Activity feed:** humanized, timestamped log of milestones ("Scene 3 visual unavailable, using curated stock imagery"). Capped at the last 30 entries, collapsible. It shows **only sanitized messages**, never request/response payloads.

**Mobile (< 768px):** graph switches to a **vertical** orientation; scene strip becomes a horizontal scroller; activity feed collapses into an expandable drawer.

### 5.3 Job View: Result (status `completed`)
- The graph **gracefully resolves** (all nodes success state), holds for ~800 ms, then collapses upward into a compact "How this was made" summary pill (expandable to show the finished graph and per-stage durations).
- The **video player** appears in a 9:16 frame (max height `min(80vh, 760px)`), centered, with a soft entrance (fade + 12px rise).
- Beside it (desktop) or below (mobile): title, topic, duration, created-at, and actions: **Download MP4** (primary), **Create another**, **Delete**.
- A **"Scenes"** row may show scene thumbnails; clicking seeks the video (SHOULD, since the backend provides scene start times in job metadata).

### 5.4 Job View: Failure (status `failed`)
- Graph frozen with the failed node in `danger` state and upstream nodes in `success`.
- Card below: **plain-language headline** ("We couldn't find visuals for scene 4"), one sentence of cause, and what's already saved ("Your script and voiceover are ready"). Primary action **Retry from this step**; secondary **Try a different topic**.
- A **collapsible "Details"** section MAY show a short sanitized `error_code` and `job_id` (to quote when debugging against `/logs/`). It MUST NOT show raw provider errors or payloads.

### 5.5 Job View: Cancelled and Interrupted
- **Cancelled:** neutral tone, offers **Start over** (same prompt prefilled).
- **Interrupted (server restart):** warning tone, offers **Resume** (maps to retry from last persisted stage).

### 5.6 Library (`/library`)
- Header: "Your creations" + count + **New video**.
- **Grid** of cards (auto-fill, min 220px). Card anatomy:
  - 9:16 thumbnail (completed), or a **status surface** (running: mini animated progress ring + current stage label; failed: muted surface with warning icon; queued: subtle shimmer).
  - Title (serif, 2 lines clamp), topic (muted, 1 line), duration badge, relative date.
  - Hover/focus: quick actions (Play, Download, Delete). Delete uses a confirm dialog.
- Filters: **All / Completed / In progress / Failed** (segmented control). Sort: newest first (fixed for MVP).
- **Empty state:** warm illustration-free typographic empty state: "Nothing here yet. Your finished videos will live here." + **Create your first video**.
- **Loading:** skeleton cards (shape-accurate, no layout shift).
- **Running cards** subscribe to a lightweight list-level refresh (poll every 5 s via TanStack Query `refetchInterval` **only while any item is running**).

### 5.7 Video Player Component
- Native `<video>` with custom controls: play/pause, scrubber with buffered range, current/total time (mono), mute/volume, fullscreen. Click to toggle play; `Space`/`K`, `←/→` (5 s seek), `M` mute, `F` fullscreen.
- `preload="metadata"`, `poster` = thumbnail, `playsInline`.
- Source: `GET /api/media/{jobId}/video` (supports HTTP Range for seeking).
- Controls auto-hide after 2.5 s of playback inactivity; always visible when paused or focused by keyboard.

---

## 6. State Management

### 6.1 Division of responsibility
| State | Owner | Why |
|---|---|---|
| Library list, job detail snapshots | **TanStack Query** | Cacheable server data |
| **Live run state** (graph, scenes, feed, status line) | **Zustand `useRunStore`** keyed by `jobId` | High-frequency, event-driven |
| UI prefs (sidebar collapsed, theme, feed open) | Zustand + `localStorage` (try/catch guarded) | Per-viewer convenience |
| Form state (composer) | Local React state | Ephemeral |

### 6.2 Run store shape (TypeScript)

```ts
type StageId = "research" | "asset" | "assembly";
type NodeId =
  | "research"
  | "asset"
  | "asset.voice"
  | "asset.visuals"
  | "assembly"
  | "assembly.compose"
  | "assembly.render"
  | "assembly.finalize";

type NodeStatus = "idle" | "active" | "retrying" | "fallback" | "success" | "failed" | "cancelled";

interface NodeState {
  id: NodeId;
  status: NodeStatus;
  label: string;            // human label from the stream or the static label table
  progress?: number;        // 0..1 if the stage reports it
  startedAt?: number;       // ms epoch (server time)
  endedAt?: number;
  badge?: "fallback" | "retry"; // sanitized hint only
}

interface SceneState {
  index: number;            // 0-based
  voice: "pending" | "active" | "done" | "failed";
  visual: "pending" | "active" | "done" | "failed";
  visualSource?: "generated" | "stock"; // provider-neutral on purpose
  imageCount?: number;
  previewUrl?: string;      // opaque media URL (§8.2)
}

interface RunState {
  jobId: string;
  jobStatus: "queued" | "running" | "completed" | "failed" | "cancelled" | "interrupted";
  title?: string;
  statusLine: string;
  nodes: Record<NodeId, NodeState>;
  scenes: SceneState[];
  feed: { id: number; at: number; text: string; tone: "info" | "warn" | "ok" }[];
  lastEventId: number;      // monotonic; used for dedupe + resume
  connection: "connecting" | "live" | "reconnecting" | "closed";
  error?: { stage: StageId; code: string; message: string; retryable: boolean };
  result?: { videoUrl: string; thumbnailUrl: string; durationSec: number };
}
```

### 6.3 Reducer rules
- A **pure reducer** `applyEvent(state, event): RunState` handles every SSE event type. It is the *only* writer.
- **Idempotent & ordered:** events with `id <= lastEventId` are dropped (handles duplicate delivery after reconnect). A gap in IDs triggers a snapshot refetch (§9.4).
- **Monotonic status:** a node never regresses from `success` to `active`, except via an explicit `retrying` event for that node.
- All incoming events are Zod-parsed first; a parse failure is logged to the console in dev, ignored in prod, and **never** crashes the UI.

---

## 7. The Node Graph (Signature Feature)

### 7.1 Topology
```
 [Research] ─────────▶ [Asset] ───────────▶ [Assembly]
                        │  ├─ Voice               │  ├─ Compose
                        │  └─ Visuals             │  ├─ Render
                        │                         │  └─ Finalize
```
- Three **stage nodes** (large) connected in sequence.
- **Asset** fans out into two **parallel sub-nodes** (*Voice*, *Visuals*) that visibly run at the same time (reflecting `asyncio.gather`), then re-converge.
- **Assembly** expands into three sub-nodes: *Compose* (timeline and motion), *Render* (encode, shows percent), *Finalize* (thumbnail, save).
- Sub-nodes are hidden/collapsed until their parent becomes `active`, then **unfurl** with a spring animation (≈ 600 ms).

### 7.2 Layout
- Fixed, hand-authored coordinates (no runtime layout engine). The graph is tiny and deterministic.
- Desktop: horizontal flow. Mobile: vertical flow. Chosen via container width, not user-agent.
- `fitView` with padding; pan/zoom/drag **disabled**; node focusable for keyboard (shows a tooltip with the node's label and status).

### 7.3 Node visual states

| Status | Visual |
|---|---|
| `idle` | Outline only, muted text, 60% opacity |
| `active` | Accent border, soft glow pulse (1.6 s loop), small animated activity glyph, progress ring if `progress` present |
| `retrying` | Warning tint, subtle shake (single, 200 ms) then gentle pulse, "Retrying" caption |
| `fallback` | Accent-soft fill with a small branch icon and caption "Using alternate source" |
| `success` | Solid success tint, check draws in (stroke animation, 300 ms) |
| `failed` | Danger border and icon, no pulse |
| `cancelled` | Muted strike style |

### 7.4 Edges
- Default: dashed neutral line.
- Edge into an `active` node: **animated flow** (dash offset marching, accent colour).
- Completed edges: solid success-tinted line.
- A tiny **"packet" dot** travels along an edge once when a stage completes and hands off to the next (conveys the data hand-off between agents). This is triggered by real `stage.completed` events, not timers.

### 7.5 Content inside nodes
Each node card contains: icon, label (e.g., "Research Agent"), a one-line humanized caption from the stream, and a status glyph.
- *Visuals* node shows `n/m scenes` count.
- *Render* node shows a determinate percent bar.
- Elapsed per node displays in mono once complete.

### 7.6 Accessibility of the graph
- The canvas is `aria-hidden="false"` with `role="img"` and an `aria-label` summarizing state ("Pipeline: Research complete, Assets in progress, Assembly waiting").
- The **status line** and **activity feed** provide the full textual equivalent. They are the screen-reader experience, so the graph is never the sole carrier of information.

### 7.7 Performance
- Memoized node components (`React.memo`) keyed by node id + status + progress bucket (round progress to 1%).
- Throttle high-frequency `progress` events to ≤ 10 renders/sec in the store (coalesce).
- Animations use `transform`/`opacity` only.

---

## 8. REST API Contract (Frontend View)

Base URL from `NEXT_PUBLIC_API_BASE_URL`. The browser talks to FastAPI **directly** (CORS locked to the frontend origin). SSE is **not** proxied through Next.js, because proxies commonly buffer streams. **All responses are Zod-validated.**

### 8.1 Endpoints

| Method | Path | Purpose | Notes |
|---|---|---|---|
| `POST` | `/api/jobs` | Create job | Body `{ prompt: string }` → `201 { jobId }` |
| `GET` | `/api/jobs` | List jobs | Newest first; `?status=` filter |
| `GET` | `/api/jobs/{jobId}` | Job snapshot | Used for rehydration and gap recovery |
| `GET` | `/api/jobs/{jobId}/events` | **SSE stream** | Supports `Last-Event-ID` |
| `POST` | `/api/jobs/{jobId}/cancel` | Cancel | Idempotent |
| `POST` | `/api/jobs/{jobId}/retry` | Retry from failed/interrupted stage | Returns `202` |
| `DELETE` | `/api/jobs/{jobId}` | Delete job + media | |
| `GET` | `/api/media/{jobId}/video` | MP4 stream | HTTP Range required |
| `GET` | `/api/media/{jobId}/thumbnail` | Poster image | |
| `GET` | `/api/media/{jobId}/scenes/{index}/preview` | Scene image preview | SHOULD; opaque, resized, no provider info |

### 8.2 Job snapshot schema (sanitized)

```ts
interface JobSummary {
  jobId: string;
  prompt: string;
  title: string | null;
  status: "queued" | "running" | "completed" | "failed" | "cancelled" | "interrupted";
  currentStage: "research" | "asset" | "assembly" | null;
  createdAt: string;            // ISO 8601
  completedAt: string | null;
  durationSec: number | null;   // video length once complete
  thumbnailUrl: string | null;  // opaque media URL
  videoUrl: string | null;
  sceneCount: number | null;
  sceneStartTimes: number[] | null; // seconds, for the Scenes row
  error: { stage: string; code: string; message: string; retryable: boolean } | null;
  lastEventId: number;          // latest event id emitted for this job
}
```
**Forbidden fields in any response:** API keys, provider names tied to secrets, request/response payloads, filesystem paths, log paths, raw exception text.

### 8.3 Error envelope
```json
{ "error": { "code": "VALIDATION_ERROR", "message": "Prompt must be 3-500 characters.", "retryable": false } }
```
The client maps `code` to localized, friendly copy (§12). The server `message` is shown only if no mapping exists.

---

## 9. SSE Contract & Client

### 9.1 Wire format
Standard SSE with a numeric `id:` per event, an `event:` type, and a JSON `data:` payload. Heartbeat comment line (`: ping`) every 15 s keeps proxies and browsers alive.

### 9.2 Event types (consumed by `applyEvent`)

| `event:` | Payload (all sanitized) | Graph effect |
|---|---|---|
| `job.snapshot` | Full `RunState`-compatible snapshot | Replace state (sent first on every connect) |
| `stage.started` | `{ stage, message }` | Node → `active` |
| `stage.progress` | `{ stage, progress, message? }` | Update ring/bar and status line |
| `stage.completed` | `{ stage, durationMs, message? }` | Node → `success`; edge handoff packet |
| `substep.started` | `{ node, message }` | Sub-node → `active` |
| `substep.progress` | `{ node, progress?, sceneIndex?, message? }` | Update sub-node, scene strip |
| `substep.completed` | `{ node, durationMs }` | Sub-node → `success` |
| `script.ready` | `{ title, sceneCount, wordCount }` | Populate title and scene strip |
| `scene.voice_ready` | `{ sceneIndex, durationSec }` | Scene chip voice → done |
| `scene.visual_ready` | `{ sceneIndex, source: "generated"\|"stock", imageCount, previewUrl? }` | Scene chip visual → done; thumbnail |
| `retry.attempt` | `{ node, attempt, maxAttempts, message }` | Node → `retrying` |
| `fallback.used` | `{ node, sceneIndex?, kind: "model"\|"visual_source", message }` | Node badge `fallback`; feed entry |
| `job.completed` | `{ videoUrl, thumbnailUrl, durationSec, sceneStartTimes }` | Resolve graph; show result |
| `job.failed` | `{ stage, code, message, retryable }` | Node → `failed`; failure screen |
| `job.cancelled` | `{}` | Cancelled state |

**Privacy rule for `fallback.used`:** `message` is human copy such as "Switched to a backup model" or "Using curated stock imagery". It never names a specific model ID, provider endpoint, or contains payload text.

### 9.3 Client behaviour (`useJobStream(jobId)`)
1. Open `EventSource(`${API}/api/jobs/${jobId}/events`)`.
2. First event is always `job.snapshot` → hydrate store.
3. On `error`: set `connection = "reconnecting"`, close, and reopen with **exponential backoff + jitter** (500 ms → 8 s cap). Native `EventSource` re-sends `Last-Event-ID` automatically on its own reconnect. When reopening manually, append `?lastEventId=` as a fallback the backend MUST also honor.
4. On terminal events (`job.completed|failed|cancelled`): close the stream and invalidate the TanStack Query job + list caches.
5. On unmount: close the stream (but never cancel the job).
6. If the connection is `reconnecting` for > 3 s, show a quiet inline note "Reconnecting…" (not an error). After 60 s of failure, show "Can't reach the server" with a Retry control while still allowing navigation.

### 9.4 Gap and race handling
- If a received `id` skips (`id > lastEventId + 1`), fetch `GET /api/jobs/{id}` and reconcile `RunState` from the snapshot, then continue.
- If the page loads for a job already `completed`, **do not open SSE**; render the result from the snapshot.
- Page Visibility: when the tab is hidden, keep the stream open (cheap). On return to visible, verify connection health and reconcile.

---

## 10. Component Architecture & Folder Structure

```
frontend/
├─ app/
│  ├─ layout.tsx                  # fonts, theme provider, query provider, shell
│  ├─ page.tsx                    # Home
│  ├─ jobs/[jobId]/page.tsx       # Job view (client boundary below)
│  ├─ library/page.tsx
│  ├─ not-found.tsx
│  └─ globals.css                 # tokens, base
├─ components/
│  ├─ shell/        Sidebar, RecentList, ThemeToggle, MobileNav
│  ├─ composer/     PromptComposer, SuggestionChips
│  ├─ job/          JobHeader, StatusLine, ActivityFeed, SceneStrip,
│  │                ResultPanel, FailurePanel, CancelDialog
│  ├─ graph/        PipelineGraph, StageNode, SubNode, FlowEdge, graphLayout.ts
│  ├─ library/      LibraryGrid, JobCard, FilterTabs, EmptyState, DeleteDialog
│  ├─ player/       VideoPlayer, Controls, Scrubber
│  └─ ui/           Button, Dialog, Toast, Skeleton, Badge, Tooltip (restyled Radix)
├─ lib/
│  ├─ api/          client.ts (fetch wrapper), jobs.ts, schemas.ts (Zod)
│  ├─ sse/          jobStream.ts (resilient client), events.ts (Zod event union)
│  ├─ state/        runStore.ts, applyEvent.ts, selectors.ts
│  ├─ copy/         errorCopy.ts, statusCopy.ts (static UI strings only)
│  └─ utils/        time.ts, format.ts
├─ styles/          tokens.css
├─ tests/e2e/       Playwright (real backend)
└─ .env.local       NEXT_PUBLIC_API_BASE_URL only
```

**Server vs client components:** pages and static chrome are Server Components; anything with SSE, Zustand, Motion, or React Flow is a Client Component. The graph is dynamically imported (`ssr: false`) with a skeleton placeholder.

---

## 11. Interaction & Micro-Animation Catalogue

| Moment | Behaviour |
|---|---|
| Composer focus | Border → accent ring fade-in (`--dur-base`) |
| Submit | Button morphs to spinner; composer dims slightly; route transition with shared-element feel (composer text becomes the job header topic) |
| Graph mount | Nodes stagger in (40 ms apart), edges draw via stroke-dashoffset |
| Stage handoff | Packet dot travels edge; next node's border animates from muted to accent |
| Sub-node unfurl | Spring expansion from parent |
| Scene thumbnail arrives | Chip cross-fades from icon to image with a 1.04→1 settle scale |
| Status line change | Vertical cross-fade (8px) |
| Completion | Checks draw in sequence → 800 ms hold → graph collapses → video rises in |
| Failure | Failed node performs a single soft shake; panel fades in below, no jarring red flood |
| Card hover | 2px lift, border darkens, actions fade in |

All durations/easings come from §4.4 tokens. No animation may block interaction or exceed 800 ms of blocking motion.

---

## 12. Error Handling & Copy

### 12.1 Principles
Empathetic, specific, action-oriented, no jargon, no blame, no raw errors (PRD §8.2).

### 12.2 Code → copy map (`errorCopy.ts`)

| `code` | Headline | Body | Primary action |
|---|---|---|---|
| `VALIDATION_ERROR` | Let's adjust that prompt | Topics need 3-500 characters. | Edit prompt |
| `PROMPT_REFUSED` | We can't make a video about that | Try a different, educational topic. | Try another topic |
| `RESEARCH_FAILED` | The script didn't come together | Our writer ran into repeated problems. Nothing was saved. | Retry |
| `VOICE_FAILED` | The voiceover failed | The script is saved. | Retry from voiceover |
| `VISUALS_UNAVAILABLE` | We couldn't find visuals for scene {n} | Your script and voiceover are ready. | Retry from visuals |
| `RENDER_FAILED` | The final render failed | Everything else is saved. | Retry render |
| `INTERRUPTED` | This run was interrupted | The server restarted mid-way. | Resume |
| `NETWORK_UNREACHABLE` | Can't reach the server | Check that the backend is running. | Retry |
| *(unknown)* | Something unexpected happened | Your job id is {id}. | Retry |

Unknown codes fall back to the last row. They never print the server message verbatim unless it passes a safe-string allow-list.

### 12.3 Toasts vs inline
Inline for form/field/job errors. Toasts only for transient confirmations (deleted, download started).

---

## 13. Accessibility, Responsiveness, Performance

**Accessibility**
- Full keyboard navigation; visible focus rings; logical tab order; skip-to-content link.
- `aria-live="polite"` for the status line; `role="status"` for connection notes; dialogs trap focus.
- Video controls labelled; captions are burned in, so no separate track is needed in MVP.
- Contrast AA across both themes; text resizable to 200%.
- `prefers-reduced-motion` and `prefers-color-scheme` honored.

**Responsive breakpoints:** 360 (min), 768, 1024, 1440. Touch targets ≥ 44px.

**Performance budgets**
- LCP < 1.8 s on Home; JS for Home < 150 KB gzip (graph and player lazy-loaded).
- No layout shift (CLS < 0.05); skeletons match final geometry.
- `next/image` is NOT used for backend media (dynamic, opaque URLs). Use plain `<img>` with explicit width/height and `loading="lazy"`.

---

## 14. Security & Privacy (Frontend)

| Control | Requirement |
|---|---|
| **Secrets** | None in the bundle, env, or network traffic. The only env var is `NEXT_PUBLIC_API_BASE_URL`. A build-time check fails CI if any `NEXT_PUBLIC_*` var matches `/key|secret|token/i` |
| **Payload exposure** | The UI never requests, stores, or renders raw prompts-to-APIs, responses, or log paths. There is **no** debug panel exposing them. Verification step: DevTools network tab inspection (PRD DoD #6) |
| **Input** | Trimmed, length-limited; rendered as text (never `dangerouslySetInnerHTML`) |
| **CSP** | `default-src 'self'`; `connect-src 'self' <API_ORIGIN>`; `media-src <API_ORIGIN>`; `img-src 'self' <API_ORIGIN> data:`; no inline script (nonce) |
| **Validation** | Zod at every boundary; reject unknown shapes silently in production |
| **Storage** | `localStorage` only for theme/sidebar prefs, wrapped in try/catch |
| **Logging** | `console.*` stripped in production build except `console.error` for unexpected parse failures (no payload content) |

---

## 15. Real-Data-Only Rules (Frontend Edition)

Mirrors PRD §9 for this layer.
- No static JSON of jobs, scripts, or events anywhere in the repo. No Storybook stories that fabricate job data.
- The **static** strings allowed are UI chrome only: headlines, chips, error copy tables, node labels.
- Suggestion chips are *input hints*, not content, and are never rendered as results.
- If the backend is unreachable, the UI shows the **real** unreachable state. It never renders a canned library.
- Library thumbnails, titles, durations always come from the backend.
- During development, run the real backend with real keys.

---

## 16. Testing Strategy (No Mocks)

| Layer | Tool | What | Data source |
|---|---|---|---|
| Pure logic (formatters, time, `errorCopy` mapping) | Vitest | Deterministic functions | Inputs computed in the test; no fabricated domain objects |
| **End-to-end** | **Playwright** | Real browser → real Next.js → real FastAPI → real Gemini/Edge-TTS/Pexels/Pixabay | Real live runs |
| Reducer/graph behaviour | Playwright | Assert DOM graph states against the **real** SSE stream | Live job |
| Accessibility | Playwright + axe-core | Home, Job (running/complete/failed), Library | Real jobs |
| Visual regression | Playwright screenshots | Home, Library empty/populated, result view | Real jobs; masks around dynamic media |
| Resilience | Playwright | Reload mid-job; offline toggle for 10 s then online; open job in second tab | Real jobs (real network interruption) |
| Failure UX | Playwright | Drive a real failure (see below) | Real failure |

**Inducing real failures without mocks:** the backend supports env-level configuration changes (e.g., first model in `LLM_MODEL_SEQUENCE` set to an invalid name; a deliberately unsatisfiable image prompt), set when launching the test backend. The frontend test asserts the real fallback badges and feed entries. Spec 3 must expose these as launch options.

**E2E acceptance scenarios**
1. Create → live graph animates through all nodes → video plays → download works (file size > 0, ffprobe duration ≤ 60 s).
2. Reload page mid-run → graph rehydrates to the exact current state without duplicate feed entries.
3. Close tab, wait, reopen via Library → shows progress or completion.
4. Cancel mid-run → state `cancelled`, no further events.
5. Failure (induced) → failure panel with correct headline and a working Retry.
6. Network `offline` for 10 s mid-run → "Reconnecting…" appears, then recovers automatically with no lost steps.
7. Network panel audit: no key-like strings, no provider hostnames, no payload fields in any request/response/event.

---

## 17. Frontend Definition of Done

- ☐ Home composer validates, submits, handles API error inline.
- ☐ `/jobs/[id]` renders live graph from the real SSE; sub-nodes unfurl; parallel Voice/Visuals visibly concurrent.
- ☐ Scene strip shows real thumbnails as visuals complete.
- ☐ Reconnect + Last-Event-ID resume verified; no duplicate/missing events (scenario 2, 6).
- ☐ Result view: custom player, Range seeking, download.
- ☐ Failure, Cancelled, Interrupted views with correct copy and working actions.
- ☐ Library: grid, filters, running-card live status, delete confirm, empty and skeleton states.
- ☐ Light/dark themes; AA contrast; reduced-motion respected; keyboard-complete.
- ☐ Network inspection shows zero secrets/payloads (scenario 7).
- ☐ No mock libraries/fixtures in repo (lint + grep check).
- ☐ Lighthouse: Perf ≥ 90, A11y ≥ 95 on Home and Library.

---

## 18. Contract Requirements Handed to Document 3 (Backend)

The backend spec MUST provide:
1. All endpoints and schemas in §8, with `Last-Event-ID` **and** `?lastEventId=` support.
2. The SSE event catalogue in §9.2, with **strictly monotonic per-job integer IDs** and a `job.snapshot` first event on every connection.
3. A **sanitizer layer** that is the *only* path from LangGraph state to SSE/REST output (allow-list, not deny-list).
4. Humanized `message` strings for each stage and fallback, provider-neutral.
5. Scene preview + thumbnail + Range-capable video routes using opaque IDs.
6. `sceneStartTimes` in the completion payload.
7. Retry-from-stage semantics and persisted stage outputs (PRD GR-03).
8. Test-launch options to induce real failures without mocks.
9. CORS locked to `FRONTEND_ORIGIN`; heartbeat every 15 s.

---

## 19. Suggested Build Order (Frontend)

1. Scaffold, tokens, fonts, theme, app shell.
2. API client + Zod schemas + TanStack Query wiring.
3. Home composer → create job → route to job page.
4. SSE client + `applyEvent` + run store (verify against a real running job, logging to console in dev).
5. Node graph with all node/edge states.
6. Scene strip, status line, activity feed.
7. Result view + custom player + download.
8. Failure/cancel/interrupted flows.
9. Library (grid, filters, live cards, delete).
10. Polish pass (motion, a11y, reduced motion, responsive), then Playwright suite.

---

*End of Document 2. Please confirm (or request changes, e.g., design tokens, graph topology, or any library choice) before I write Document 3: Backend & Architecture Specification.*
