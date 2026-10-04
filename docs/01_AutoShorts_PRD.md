# AutoShorts: Product Requirements Document (PRD)

**Document 1 of 3** | WCC Launchpad 30, Agentic AI Track
**Status:** Draft v1.0 for confirmation
**Build environment:** Antigravity
**Companion docs:** (2) Frontend Specification, (3) Backend & Architecture Specification

---

## 0. How to Read This Document

This PRD defines **what** we are building and **what "good" means**. It deliberately avoids implementation detail that belongs in the Frontend and Backend specs. Every requirement has an ID (e.g., `FR-12`, `GR-04`) so Antigravity, tests, and the other two specs can reference it unambiguously. Keywords **MUST**, **SHOULD**, **MAY** follow RFC 2119 meaning.

---

## 1. Product Vision

### 1.1 One-liner
**AutoShorts turns one sentence into a finished, narrated, subtitled, 60-second vertical educational video, with no human editing.**

### 1.2 Vision statement
A learner, teacher, or creator types a topic ("Why is the sky blue?"). A team of cooperating AI agents researches it, writes a tightly-timed script, voices it, finds or generates visuals, and edits everything into a polished 9:16 video. The user watches a live node graph of the agents working, then receives a video they would be comfortable posting publicly.

### 1.3 Why this wins in an Agentic AI track
| Judging lens | How AutoShorts demonstrates it |
|---|---|
| Real agency | Three specialized agents with typed hand-offs, retries, and self-correction (e.g., script too long, so the agent rewrites it) |
| Orchestration | LangGraph state machine with streamed, observable state |
| Robustness | Multi-model LLM failover; image-generation-to-stock fallback; no mock data ever |
| Transparency | Live node-graph progression plus complete local API audit logs |
| Output quality | High-fidelity render with animated, lively visuals, not a slideshow |
| Product polish | Claude-grade minimalist UI, a persistent library, and graceful errors |

---

## 2. Problem & Opportunity

- **Problem:** Short-form educational video is high-impact but expensive to produce. Scripting, voiceover, sourcing visuals, and editing take hours per clip.
- **Gap in existing AI tools:** Most "text-to-video" demos are either (a) opaque black boxes with no insight into progress, (b) brittle, failing on the first API error, or (c) visually flat, with a static image and robotic captions. They feel like prototypes.
- **Opportunity:** A pipeline that is transparent, resilient, and visually dynamic can feel like a product rather than a demo, even at MVP scope.

---

## 3. Target Audience

### 3.1 Primary personas

**P1: "The Curious Learner" (Ananya, 19, university student)**
- Wants quick visual explanations of concepts for revision.
- Success: types a topic, gets a watchable explainer in a few minutes.

**P2: "The Solo Educator / Creator" (Rahul, 32, tutor and YouTuber)**
- Wants vertical clips for Shorts/Reels without learning an editor.
- Success: output is good enough to post with zero or minimal touch-up.

**P3: "The Hackathon Judge" (evaluator, time-poor, skeptical)**
- Will try 1-3 prompts in a few minutes and look for cracks.
- Success: sees an impressive, honest system that handles edge cases and shows its internals tastefully.

### 3.2 Explicit non-targets (MVP)
Enterprise teams, multi-user collaboration, branded template management, and non-educational video genres.

---

## 4. MVP Scope

### 4.1 In scope (MUST ship)
1. Single-prompt video creation, producing a 9:16 MP4 of up to 60 seconds.
2. Three-agent LangGraph pipeline: **Research, Asset, Assembly**.
3. Gemini-only LLM layer behind a **custom failover gateway** (5-model sequence).
4. Parallel asset generation: **Edge-TTS** audio plus **image generation** with **Pexels/Pixabay smart fallback**.
5. MoviePy assembly with synced subtitles, animated motion, and high-quality encoding.
6. **Live SSE progress** and an animated **node-graph** tracker.
7. A **Library** ("My Creations") for viewing, replaying, downloading, and deleting past videos.
8. **Local API audit logging** of every external call, raw request and response.
9. Secure key handling: keys live only in backend `.env`, never in the browser.

### 4.2 Out of scope (explicitly NOT in MVP)
- User accounts, auth, billing, or multi-tenancy (single local user; see Open Questions).
- Video-clip stock footage (images only).
- Background music generation or licensing flows (see Open Questions).
- Manual timeline editing, script editing before render, or multi-language support beyond what Edge-TTS voice selection gives for free.
- Cloud deployment, CDN, or horizontal scaling.
- Mobile-native apps (the web UI MUST be responsive, but no native app).
- Publishing/upload integrations to YouTube/Instagram.

### 4.3 Stretch (only after all MUST items pass acceptance)
- Voice picker (a small curated list of Edge-TTS voices).
- Style presets (e.g., "Clean Minimal", "Cinematic", "Playful") that adjust palette, font, and motion.
- Regenerate-scene action.

---

## 5. Core User Flow

### 5.1 Happy path

| Step | User sees | System does |
|---|---|---|
| 1 | Minimal home with a centered prompt box, subtle example chips, and a sidebar link to **Library** | Idle |
| 2 | Types a topic and presses **Enter / Create** | Backend creates a `job_id`, persists the job as `queued`, opens an SSE stream |
| 3 | View transitions to the **Generation Screen** with an animated node graph (Research → Asset → Assembly, with sub-nodes) | LangGraph begins streaming state updates |
| 4 | **Research node** pulses; a short human-readable status line appears (e.g., "Writing a 58-second script…") | Research Agent calls the LLM Gateway and validates a strict schema |
| 5 | **Asset node** splits into parallel sub-nodes: *Voiceover*, *Visuals* (with per-scene mini-progress) | `asyncio.gather` runs TTS and image generation; fallbacks trigger if needed |
| 6 | **Assembly node** shows render progress (scene count, percent) | MoviePy composes, animates, subtitles, and encodes |
| 7 | Graph resolves to a completed state; the video appears with a smooth transition | Job marked `completed`; MP4, thumbnail, and metadata saved |
| 8 | User can **Play**, **Download**, **Create another**, or find it in **Library** | none |

### 5.2 Alternate and error flows

| Scenario | Expected behaviour |
|---|---|
| Empty or too-short prompt | Inline validation; the Create button stays disabled; no job is created |
| Prompt is unsafe/unsuitable (policy refusal from LLM) | Pipeline halts at Research with a clear, kind message and a "Try a different topic" action. No placeholder video |
| LLM model fails | Gateway silently advances to the next model; UI may show a subtle "retrying" micro-state but never raw errors |
| Image generation fails for a scene | Smart fallback fetches multiple stock images for that scene; the node shows a "fallback" badge |
| Both image generation and stock fail for a scene | Retry with broadened keywords; if still failing, the job fails explicitly at that scene (see §9.4). **No mock/placeholder imagery** |
| Browser tab closed mid-generation | Job continues in the background; the user returns via Library and sees "In progress" with a reconnectable live view |
| SSE connection drops | Frontend auto-reconnects and resumes from the last event ID without duplicating or losing steps |
| Hard failure (all retries exhausted) | A calm failure screen: which stage failed, plain-language reason, **Retry** button (restarts only from the failed stage when possible) |

---

## 6. Functional Requirements

### 6.1 Input & Job Management
- **FR-01** The system MUST accept a free-text topic prompt (min 3 characters, max 500).
- **FR-02** Each submission MUST create a unique job with a stable `job_id`.
- **FR-03** Jobs MUST run in the background, decoupled from the HTTP request and the browser tab.
- **FR-04** The system MUST support at least **2 concurrent jobs** without cross-contamination of state, files, or logs.
- **FR-05** A user MUST be able to cancel an in-flight job; cancellation MUST stop further paid/limited API calls promptly.

### 6.2 Node 1: Research Agent
- **FR-10** The agent MUST use the LLM Gateway (never a direct model call).
- **FR-11** It MUST output a **strictly validated Pydantic schema** representing a 60-second timeline.
- **FR-12** Total narration MUST be **120-140 words** (hard bounds, validated in code, not just prompted).
- **FR-13** The timeline MUST contain **5-8 scenes**; each scene includes: narration text, a visual intent (what should be on screen), an image-generation prompt, 3-6 stock-search keyword sets (ordered specific to generic), and an on-screen emphasis phrase.
- **FR-14** The script MUST open with a hook in the first scene and close with a clear takeaway.
- **FR-15** If schema validation or the word-count check fails, the agent MUST self-correct (re-prompt with the validation error) up to a bounded number of attempts before failing explicitly.
- **FR-16** Content MUST be factually grounded to the extent the model can manage; the prompt MUST instruct the model to avoid unverifiable specifics (invented statistics, fake quotes).

### 6.3 Node 2: Asset Agent
- **FR-20** TTS and visual generation MUST execute **concurrently** via `asyncio.gather`.
- **FR-21 (Voice)** Edge-TTS MUST produce one audio track per scene, or one track plus accurate timing metadata, so that scene durations can be locked to real audio length.
- **FR-22 (Voice)** The system MUST capture word- or sentence-level timing data for subtitle synchronization.
- **FR-23 (Visuals, primary)** For each scene, the system MUST attempt AI image generation at **9:16 portrait** resolution.
- **FR-24 (Visuals, fallback)** On any image-generation failure (error, safety block, timeout, empty result), the system MUST automatically query **Pexels first, then Pixabay** (or the reverse, as the Backend Spec defines) using the scene's context-specific keywords.
- **FR-25** The fallback MUST fetch **multiple** images per scene (target **3-5**, as many as needed) so the Assembly stage can create lively motion within a scene.
- **FR-26** Fetched stock images MUST be filtered for portrait suitability (orientation and minimum resolution) and de-duplicated across scenes.
- **FR-27** Each scene's final asset record MUST state which source produced each image (`generated`, `pexels`, `pixabay`) for traceability.
- **FR-28** Attribution metadata (photographer, source URL) for stock images MUST be stored with the job, even if not rendered in the MVP video.

### 6.4 Node 3: Assembly Agent
- **FR-30** MoviePy MUST lock each scene's visual duration to its real audio duration.
- **FR-31** Within a scene with multiple images, durations MUST be subdivided so the visuals change in rhythm with narration.
- **FR-32** Every image MUST receive **non-static motion** (see §8 motion standards).
- **FR-33** Subtitles MUST be burned in, synchronized to speech, readable, and styled (see §8).
- **FR-34** Output MUST be 1080x1920, H.264/AAC MP4, with **high-quality encoding settings** (no low-quality presets; render time is explicitly secondary to quality).
- **FR-35** A thumbnail (poster frame) MUST be generated for the Library.
- **FR-36** Final duration MUST be **≤ 60.0 seconds**. If it would exceed this, the system MUST correct upstream (tighten script or adjust TTS rate within limits), not truncate abruptly.

### 6.5 Streaming & Progress
- **FR-40** FastAPI MUST stream LangGraph state updates via **SSE**.
- **FR-41** Events MUST be granular enough to animate sub-steps (e.g., "scene 3 of 6: generating image", "scene 3: fallback to stock").
- **FR-42** Events MUST be **sanitized**: only user-safe fields (stage, status, human-readable message, progress numbers, non-sensitive metadata). Never keys, raw prompts to APIs, raw responses, or internal URLs.
- **FR-43** Events MUST carry monotonic IDs to support resume after reconnect.

### 6.6 Library ("My Creations")
- **FR-50** All jobs (queued, running, completed, failed) MUST appear in the Library, newest first.
- **FR-51** Completed items MUST show thumbnail, title, topic, duration, and creation time.
- **FR-52** The user MUST be able to play inline, download MP4, and delete an item (removing its files; audit logs behave per §10.3).
- **FR-53** Running items MUST re-open into the live node-graph view.
- **FR-54** Failed items MUST show the failed stage and offer **Retry**.

### 6.7 Logging & Observability
- **FR-60** **Every** external API call (Gemini LLM, Edge-TTS, image generation, Pexels, Pixabay) MUST write its **raw request and raw response** to local disk under `/logs/api_calls/`.
- **FR-61** Logs MUST be organized per job (and per call), include timestamps, latency, model/provider, attempt number, and outcome, and MUST be written even for failed calls.
- **FR-62** Binary payloads (audio, images) MUST be stored as files with the log entry referencing the path (plus size and hash).
- **FR-63** API keys MUST be **redacted** from logged request headers and URLs (keys never written to logs in plaintext).
- **FR-64** None of this log data MUST be reachable through any frontend-facing API route.

---

## 7. LLM Gateway: Product-Level Requirements

(Implementation detail lives in the Backend Spec.)

- **GW-01** Models are used strictly in this fallback order unless the Backend Spec justifies a reorder:
  1. `gemini-3.5-flash`
  2. `gemini-3.5-flash-lite`
  3. `gemini-3.6-flash`
  4. `gemini-3.7-flash`
  5. `gemini-3.8-flash`
- **GW-02** Any error class that indicates a transient or capacity problem (rate limit/429, 5xx, timeout, overloaded, empty/blocked response) MUST trigger automatic advancement to the next model **within the same request**, transparent to the calling agent.
- **GW-03** Non-recoverable client errors (e.g., invalid key, malformed request caused by our code) MUST be surfaced loudly and not blindly cycled across all models.
- **GW-04** If all five models fail, the gateway MUST apply bounded retry with backoff over the whole sequence, then raise a typed exception. It MUST NOT return canned or default text.
- **GW-05** Every attempt, including each failed model, MUST be logged (FR-60).
- **GW-06** The model list MUST be config-driven (env or config file) so it can be corrected without code changes. *(Note: model identifiers are used exactly as provided by the team; startup validation should confirm each is reachable and warn clearly if not.)*

---

## 8. Quality Bar: Making It Not Feel Like a Prototype

### 8.1 Visual output standards
| Dimension | Standard |
|---|---|
| Resolution | 1080x1920 (9:16), 30 fps (60 fps NOT required) |
| Encoding | H.264 High profile, slow preset, low CRF (visually lossless-ish), AAC 192 kbps+; final values specified in Backend Spec |
| Motion | Every image has continuous motion: slow zoom (Ken Burns) with varied direction/anchor, subtle pan, eased with smooth curves, never linear robotic zoom |
| Transitions | Crossfades or soft push transitions between images/scenes; no hard jump cuts unless intentional |
| Variety | Adjacent images MUST NOT use the same motion vector; motion is deterministically varied per image |
| Pacing | Image change cadence tied to narration phrasing (roughly every 2-4 seconds), never a single image sitting for more than ~5 seconds |
| Subtitles | Large, high-contrast, safe-zone-aware (clear of platform UI areas), with word- or phrase-level highlight/pop animation, soft shadow or backing for legibility on any image |
| Emphasis text | The scene's key phrase animates in (fade/slide/scale) and exits cleanly |
| Color/consistency | Consistent type system; consistent subtle vignette/overlay to keep text readable across varied images |
| Audio | Normalized loudness; no clipping; clean start and end (short fade) |
| Aspect handling | Source images are intelligently cover-cropped to 9:16 (no stretching, no letterbox bars) |

### 8.2 UI/UX standards
- Minimalist, warm, content-first; visual language inspired by Claude, with influences from ChatGPT and Gemini (calm neutrals, generous whitespace, refined typography, soft motion).
- No spinner-only waiting. The user always sees **what is happening and why**.
- Skeleton and optimistic states; no layout shift; keyboard accessible; respects `prefers-reduced-motion`; WCAG AA contrast.
- Errors are human, specific, and actionable. No stack traces, no JSON dumps, no "Something went wrong" alone.
- Dark and light themes.

### 8.3 Engineering guardrails (anti-jank)
- **GR-01** Every external call has: timeout, bounded retries with exponential backoff and jitter, and a defined fallback path or explicit failure.
- **GR-02** All inter-agent data flows through **typed Pydantic models**; no free-form dict passing.
- **GR-03** Stage outputs are **idempotent and persisted** so retries resume from the failed stage rather than restarting everything.
- **GR-04** Resource hygiene: temp files cleaned up; no zombie render processes; memory-safe handling of large frames.
- **GR-05** No silent failures. Every caught exception is logged and either recovered via a defined fallback or escalated.
- **GR-06** Strict separation: the frontend knows nothing about providers, keys, or raw payloads.
- **GR-07** Observable by default: structured application logs (separate from API payload logs) with `job_id` correlation.
- **GR-08** Deterministic-where-possible: seeds or recorded parameters for motion choices so a render can be reproduced from stored metadata.

---

## 9. The No-Mock-Data Policy (Non-Negotiable)

### 9.1 Statement
> The system MUST NEVER substitute mock, placeholder, sample, cached-demo, or default content for real generated content, in tests, in development, or in production.

### 9.2 What "defensive" means here
When something fails, the correct behaviour is, **in order**:
1. **Retry** the same operation (bounded, with backoff).
2. **Fall back** to an alternative *real* source (next Gemini model; stock images instead of generated images; alternate stock provider; broadened keywords).
3. **Fail explicitly and visibly**, with a clear reason and a Retry option.

Substituting fake data is never step 3.

### 9.3 Prohibited
- Hardcoded sample scripts, canned narrations, or pre-baked "demo" videos.
- Solid-color or gradient "stand-in" images presented as scene visuals.
- Mocked HTTP responses, patched API clients, or recorded-fixture replay in the test suite.
- Frontend fixtures that fabricate library items or progress.

### 9.4 Explicit-failure rule for visuals
If a scene ends with **zero** valid real images after generation + both stock providers + keyword broadening, the job MUST fail at the Asset stage with a scene-level error. A video with a missing scene visual is **not** an acceptable output.

### 9.5 Testing rule
- All tests, including integration and end-to-end, MUST make **real API calls** with real keys from the `.env`.
- Test assertions verify real outputs (schema validity, word counts, file existence, media duration via ffprobe, log completeness).
- Tests that need to exercise failure paths MUST induce failure through real mechanisms (e.g., an intentionally invalid model name or a deliberately impossible image prompt), not by mocking.
- Every test run's `/logs/api_calls/` output is the evidence artifact.

---

## 10. Non-Functional Requirements

### 10.1 Performance
- Quality over speed in rendering, but the user experience of waiting must be excellent. Target end-to-end time for a typical job: **3-8 minutes** on a standard dev machine. No hard SLA, but the UI MUST show meaningful progress at least every few seconds.
- Time-to-first-SSE-event after submit: **< 1 second**.

### 10.2 Reliability
- Pipeline success rate target on a set of 20 diverse real prompts: **≥ 95%** without manual intervention.
- Zero unhandled exceptions reaching the user as raw errors.

### 10.3 Security & Privacy
- API keys exist **only** in backend environment variables; never in frontend bundles, responses, SSE events, or logs.
- `/logs/` and `.env` are git-ignored.
- Media-serving routes expose only final MP4s and thumbnails, by opaque IDs, never filesystem paths.
- CORS restricted to the frontend origin.
- Input is sanitized; prompts are length-limited; basic abuse/rate limiting on job creation.
- Deleting a Library item deletes its media. API audit logs are retained for debugging unless the developer purges them manually (the logs are developer-facing, never user-facing).

### 10.4 Compatibility
- Frontend: latest Chrome, Safari, Firefox, Edge; responsive from 360px to desktop.
- Backend: Python 3.11+; FFmpeg required on PATH (checked at startup with a clear error).

### 10.5 Licensing
- Pexels and Pixabay content is used per their API terms. Attribution metadata is stored. Both providers' API usage limits must be respected (the gateway must handle their rate limits gracefully).

---

## 11. Failure & Recovery Matrix

| Failure | Detection | Recovery (in order) | Terminal behaviour |
|---|---|---|---|
| Gemini 429/5xx/timeout/empty | HTTP/SDK error | Next model in sequence, same request | After full cycle + backoff, typed error, job fails at Research with Retry |
| Script wrong word count / bad schema | Pydantic + custom validators | Re-prompt with validator feedback (bounded) | Job fails at Research |
| Edge-TTS connection error | Exception/timeouts | Retry with backoff; alternate configured voice | Job fails at Asset (voice) |
| Image gen error/safety block/timeout | Provider error/empty | Rewrite prompt (softened) once; then stock fallback | → stock fallback |
| Stock provider A empty/error | API result | Provider B; broaden keywords (specific → generic) | Scene-level failure if zero images |
| Downloaded image corrupt/too small/wrong ratio | Validation (PIL) | Discard, fetch next candidate | Continue; fail only if below minimum image count |
| Audio longer than 60s | Duration check post-TTS | Ask Research Agent to tighten script, or adjust TTS rate within limit | Job fails at Asset if irreconcilable |
| MoviePy/FFmpeg error | Exception/exit code | Retry render once with clean temp dir | Job fails at Assembly with Retry |
| SSE disconnect | Client event | Auto-reconnect with Last-Event-ID | n/a (stateless to the user) |
| Server restart mid-job | Startup recovery scan | Mark interrupted jobs; allow resume from last persisted stage | Job shown as "Interrupted" with Retry |

---

## 12. Configuration & API Key Block

The user will paste real keys here. The Backend Spec will wire these through a typed settings loader. **Keys are never exposed to the frontend.**

```dotenv
# ============================================================
# AutoShorts Backend Environment (backend/.env)
# DO NOT COMMIT THIS FILE. It is git-ignored.
# ============================================================

# --- API KEYS (paste yours below) ---------------------------
GEMINI_API_KEY=PASTE_YOUR_GOOGLE_GEMINI_KEY_HERE
PEXELS_API_KEY=PASTE_YOUR_PEXELS_KEY_HERE
PIXABAY_API_KEY=PASTE_YOUR_PIXABAY_KEY_HERE

# --- LLM GATEWAY (ordered fallback sequence) ----------------
LLM_MODEL_SEQUENCE=gemini-3.5-flash,gemini-3.5-flash-lite,gemini-3.6-flash,gemini-3.7-flash,gemini-3.8-flash
LLM_REQUEST_TIMEOUT_SECONDS=60
LLM_MAX_FULL_CYCLES=3

# --- IMAGE GENERATION (Gemini-family image model; see Open Question OQ-1) ---
IMAGE_GEN_MODEL=SET_AFTER_CONFIRMING_AVAILABLE_IMAGE_MODEL
IMAGE_GEN_ASPECT_RATIO=9:16

# --- TTS (Edge-TTS needs no API key) ------------------------
TTS_VOICE=en-US-AndrewMultilingualNeural
TTS_RATE=+0%

# --- VIDEO OUTPUT -------------------------------------------
VIDEO_WIDTH=1080
VIDEO_HEIGHT=1920
VIDEO_FPS=30
VIDEO_MAX_SECONDS=60

# --- PATHS --------------------------------------------------
LOG_DIR=./logs/api_calls
MEDIA_DIR=./storage
DB_PATH=./storage/autoshorts.db

# --- SERVER -------------------------------------------------
FRONTEND_ORIGIN=http://localhost:3000
```

The frontend's own `.env.local` contains **only** the backend base URL (e.g., `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`), never any secret.

---

## 13. Success Metrics & Acceptance Criteria

### 13.1 Product metrics (for demo and judging)
| Metric | Target |
|---|---|
| Prompt-to-video success rate (20 real prompts) | ≥ 95% |
| Videos judged "postable" by a blind reviewer panel | ≥ 80% |
| Mean user-visible "dead time" (no UI change) | < 5 seconds |
| Fallback demonstrations (induced real failures) all recover | 100% |

### 13.2 Definition of Done (MVP acceptance checklist)
1. ☐ Typing a prompt produces a ≤ 60s, 1080x1920 MP4 with synced audio, visuals, and subtitles.
2. ☐ Script is always 120-140 words and schema-valid (verified in code).
3. ☐ Forcing the primary Gemini model to fail (via a real invalid model name as the first entry) yields successful completion through a later model, and **all attempts appear in logs**.
4. ☐ Forcing image generation to fail yields stock fallback with **multiple images per scene** and visibly lively motion.
5. ☐ Every API call in a full run has a request and response artifact in `/logs/api_calls/<job_id>/`.
6. ☐ A network inspection of the browser shows **no keys, no provider URLs, no raw payloads**.
7. ☐ Node graph animates in real time through all stages and sub-steps; reconnect works mid-job.
8. ☐ Library lists, plays, downloads, deletes, and re-opens in-progress jobs.
9. ☐ Codebase contains **zero** mocks, fixtures, or fabricated sample data (grep-verified).
10. ☐ Reduced-motion and keyboard navigation pass a manual check.
11. ☐ ffprobe confirms codec, resolution, bitrate, and duration of the output.

---

## 14. Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Specified Gemini model identifiers not all available on the key | Gateway cycles through unavailable models, adding latency | Startup preflight check; config-driven sequence; clear warning logs |
| Image-generation capability/quota on a free-tier key | Frequent fallbacks | Fallback is a first-class path, not an exception; design visuals to look great with stock too |
| Stock images feel generic or irrelevant | Weak output quality | Ordered keyword sets (specific to generic) authored by the Research Agent; relevance filtering; diversity across scenes |
| MoviePy rendering is slow at high quality | Long waits | Rich progress UI; background jobs; make waiting feel purposeful |
| Edge-TTS is an unofficial service and can be flaky | Voice stage failures | Retries, alternate voice fallback, clear error surface |
| Subtitle/audio desync | Looks amateurish | Use real timing metadata; validate offsets in tests |
| Scope creep | Missed deadline | Strict MUST/Stretch split above |
| Time budget of the hackathon | Incomplete polish | Build order: vertical slice (prompt → video) first, then streaming UI, then polish |

---

## 15. Assumptions & Open Questions

**Assumptions**
- A1. Single local user; no auth needed for the hackathon demo.
- A2. English-language content for the MVP.
- A3. Developer machine has FFmpeg and enough CPU/RAM for 1080x1920 rendering.
- A4. Model names are as provided by the team and are the source of truth.

**Open Questions (answers will be baked into Specs 2 and 3 unless you correct them)**
- **OQ-1: Image generation provider.** You listed three keys (Gemini, Pexels, Pixabay). I am assuming "image generation" uses a **Gemini-family image-capable model on the same Gemini key**, configurable via `IMAGE_GEN_MODEL`. Please confirm, or name the specific model you intend to use. If image generation isn't available on your key, the system still works (stock fallback is complete), but the primary path would be effectively disabled.
- **OQ-2: Background music.** Not in MVP because no music provider/key was specified. Silence beneath narration is acceptable for MVP; confirm, or point me at a music source.
- **OQ-3: Persistence.** I'm assuming **SQLite** for job metadata and the local filesystem for media. Confirm.
- **OQ-4: Voice.** Default to a single high-quality English Edge-TTS voice, with a voice picker as a stretch goal. Confirm.
- **OQ-5: Parallelism target.** Concurrent job limit of 2 for the demo. Confirm.

---

## 16. Document Roadmap

| Doc | Contents | Depends on this PRD for |
|---|---|---|
| **2. Frontend Spec** | Next.js architecture, design system, routes, SSE client, node-graph state machine, Library, accessibility | Flows (§5), FR-40-54, UX standards (§8.2), security (§10.3) |
| **3. Backend & Architecture Spec** | FastAPI, LLM Gateway, LangGraph state/nodes, Pydantic schemas, Asset/Media engine, MoviePy recipes, logging subsystem, persistence, testing harness | FR-10-36, FR-60-64, GW-01-06, §9, §11, §12 |
| **Master Prompt** | Single Antigravity kickoff prompt synthesizing all three | All |

---

*End of Document 1. Awaiting your confirmation (and answers to the Open Questions, if you want to change any assumptions) before Document 2: Frontend Specification.*
