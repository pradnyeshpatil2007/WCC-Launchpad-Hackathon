# AutoShorts Implementation Plan & Verification Matrix

**Project:** AutoShorts (WCC Launchpad 30, Agentic AI Track)  
**Spec Precedence:** Doc 3 §0 (R1-R5) > Doc 1 (PRD); Doc 2 (UI); Doc 3 (Backend).  
**Amendment Applied:** Pollinations.ai API (`https://gen.pollinations.ai/image/{prompt}?width=1080&height=1920&model=flux&nologo=true`) replaces Gemini Image Gen; `IMAGE_GEN_MODEL_SEQUENCE` removed from required `.env`; falls back to Pexels and Pixabay.

---

## 1. System Architecture & Flow

```
User Prompt (3-500 chars)
  │
  ▼
[FastAPI Backend / JobRunner (concurrency=2)]
  │
  ├─► Node 1: Research Agent (LangGraph)
  │     └─► LLM Gateway (gemini-3.5-flash → lite → 3.6 → 3.7 → 3.8)
  │           └─► Validated Script (120-140 words, 5-8 scenes, 2-3 visual beats/scene)
  │
  ├─► Node 2: Asset Agent (asyncio.gather)
  │     ├─► Voice Branch (Edge-TTS word/sentence timing, loudnorm -16 LUFS, duration budget check)
  │     └─► Visuals Branch (Pollinations.ai flux 9:16 → Pexels → Pixabay → Query Repair, de-dup phash)
  │
  └─► Node 3: Assembly Agent (MoviePy 2.x + FFmpeg Subprocess)
        ├─► TimelineBuilder (smoothstep Ken Burns, safe zones, 2-4 word animated pop captions)
        ├─► Subprocess render with progress queue (x264 slow, crf 16, aac 192k)
        └─► ffprobe verification & 540x960 thumbnail generation
  │
  ▼
Next.js 15 Frontend
  ├─► SSE Stream (/api/jobs/{id}/events with Last-Event-ID resume & monotonic seq)
  ├─► Animated Node Graph (React Flow with active pulse, packets, parallel sub-nodes)
  ├─► Humanized status & Activity feed (no secrets, no internal payloads)
  └─► Library & 9:16 Video Player (HTTP Range 206 seeking, download)
```

---

## 2. Guardrails & Non-Negotiable Rules

1. **NO MOCK DATA**: Zero `unittest.mock`, `pytest-mock`, `msw`, `faker`, or canned fixtures. All tests use real endpoints.
2. **AUDIT LOGGING**: Every outbound HTTP/TTS call logged under `logs/api_calls/<job_id>/` with `request.json`, `response.json`, `meta.json`, externalized binaries, and redacted keys.
3. **SECRETS LEAK GUARD**: `NEXT_PUBLIC_API_BASE_URL` is the only frontend env variable. Backend sanitizer validates all outgoing SSE/REST payloads.
4. **FAIL-CLOSED**: If audit log writing fails under `LOG_FAIL_CLOSED=true`, the call aborts with `AUDIT_LOG_FAILURE`.

---

## 3. Phase Breakdown & File-by-File Task List

### Phase 0: Scaffold & Guardrails (Gate 0 ⛔)
- **Files to create:**
  - `.gitignore` (ignore `backend/.env`, `logs/`, `storage/`, `node_modules/`, `.next/`, `__pycache__/`)
  - `backend/.env.example` & `backend/.env` template (Doc 3 §4.1 + Pollinations amendment)
  - `backend/app/config.py`: Pydantic Settings with fail-fast validation and SecretStr masking
  - `backend/requirements.txt`: FastAPI, Uvicorn, LangGraph, Pydantic, httpx, edge-tts, Pillow, MoviePy, aiosqlite, structlog, pytest, etc.
  - `scripts/doctor.py`: Environment readiness check (Python 3.11+, FFmpeg, ffprobe, fonts, writable directories)
  - `scripts/check_no_mocks.sh` / `scripts/check_no_mocks.py`: Scans repo for banned mock libraries and mock data
  - `scripts/check_secrets.sh` / `scripts/check_secrets.py`: Scans tracked files, logs, and frontend bundles for leaked keys/tokens
  - `backend/assets/fonts/`: Bundle OFL fonts (Inter ExtraBold / Montserrat, Newsreader, Geist Mono) + LICENSE files
  - `docs/verification.md`: Skeleton for live probe notes
- **Verification Command:** `python scripts/doctor.py && python scripts/check_no_mocks.py && python scripts/check_secrets.py`
- **Gate 0:** Prompt user to paste keys (`GEMINI_API_KEY`, `PEXELS_API_KEY`, `PIXABAY_API_KEY`) into `backend/.env`. Stop until confirmed.

---

### Phase 1: Audit Logging, Persistence & Startup Preflight
- **Files to create:**
  - `backend/app/core/ids.py`: ULID generator for jobs and sequential call ids
  - `backend/app/core/audit_log.py`: `AuditLogger`, redaction engine, binary externalizer, `index.jsonl` writer, fail-closed handling
  - `backend/app/core/http_client.py`: `LoggedHttpClient` wrapping `httpx.AsyncClient`
  - `backend/app/providers/tts.py`: `LoggedEdgeTTS` wrapping `edge_tts.Communicate`
  - `backend/app/jobs/models.py`: SQLAlchemy async models (`jobs`, `stages`, `events`)
  - `backend/app/jobs/repo.py`: SQLite async repository (WAL mode, foreign keys)
  - `backend/app/preflight.py`: Startup checks for models, Pexels, Pixabay, Edge-TTS logged to `logs/api_calls/_system/`
  - `backend/tests/test_audit_log.py`: Real call audit logging, binary extraction, secret redaction, and fail-closed test
- **Verification Command:** `pytest backend/tests/test_audit_log.py -v -s`

---

### Phase 2: LLM Gateway
- **Files to create:**
  - `backend/app/llm/classify.py`: Error classifier (transient 429/5xx -> ADVANCE, auth 400/401 -> FATAL, prompt blocked, bad json)
  - `backend/app/llm/gemini_rest.py`: Direct REST request/response shaping, JSON schema inliner (`to_gemini_schema`)
  - `backend/app/llm/gateway.py`: `LLMGateway` with sequential failover (`gemini-3.5-flash` down to `gemini-3.8-flash`), per-model cooldowns, full-cycle backoff, deadline enforcement
  - `backend/tests/test_gateway.py`: Real live test exercising invalid first model -> 404 -> advance -> success, fatal auth check, exhaustion check
- **Verification Command:** `pytest backend/tests/test_gateway.py -v -s`

---

### Phase 3: Research Agent
- **Files to create:**
  - `backend/app/domain/script.py`: Pydantic models `Script`, `Scene`, `VisualBeat` with regex word-count validator (120-140 words, 5-8 scenes, 2-3 beats/scene)
  - `backend/app/prompts/research_system.md`: Scriptwriting prompt with safety delimiters, concrete metaphors, stock query guidelines
  - `backend/app/graph/research.py`: Research node with self-correction repair loop (re-prompting on validation error up to 3 times) and tighten feedback handler
  - `backend/tests/test_research.py`: Live generation across 5 diverse topics asserting strict word count and schema validity
- **Verification Command:** `pytest backend/tests/test_research.py -v -s`

---

### Phase 4: Asset Agent (Audio & Visuals)
- **Files to create:**
  - `backend/app/domain/assets.py`: `WordTiming`, `SceneAudio`, `VoiceManifest`, `AcceptedImage`, `SceneVisuals`, `VisualManifest`
  - `backend/app/providers/image_gen.py`: Pollinations.ai Flux 9:16 client via `LoggedHttpClient`
  - `backend/app/providers/pexels.py`: Pexels portrait search & downloader with rate-limit tracking
  - `backend/app/providers/pixabay.py`: Pixabay vertical search & downloader
  - `backend/app/providers/stock.py`: Unified stock search, ranking, and downloading
  - `backend/app/media/imaging.py`: PIL image validation, cover crop, perceptual hash (phash), Sobel saliency focal-point centroid
  - `backend/app/media/audio.py`: Concatenation, gap insertion, ffmpeg 2-pass `loudnorm` to -16 LUFS
  - `backend/app/graph/asset.py`: `asyncio.gather(run_voice, run_visuals)` with Query Repair (R5), scene top-up, previews (270x480), and atomic stage persistence
  - `backend/tests/test_asset.py`: Live parallel test, forced image failure -> stock fallback, and provider failover
- **Verification Command:** `pytest backend/tests/test_asset.py -v -s`

---

### Phase 5: Assembly Agent & Media Engine (Gate 5 ⛔)
- **Files to create:**
  - `backend/app/domain/timeline_models.py`: `Timeline`, `Shot`, `MotionPreset`, `CaptionPage`, `EmphasisOverlay`
  - `backend/app/media/timeline.py`: Pure timeline builder tying shots to word boundary timestamps
  - `backend/app/media/motion.py`: Easing math (smoothstep/cubic), floating-point Ken Burns box, handheld organic drift
  - `backend/app/media/captions.py`: High-DPI Pillow 2-4 word chunking, pop active word highlight, safe zone layout
  - `backend/app/media/overlays.py`: Vignette, scrim, emphasis text animation
  - `backend/app/media/render_worker.py`: Subprocess entrypoint (`spawn`), MoviePy 2.x x264 encode (slow, crf 16, aac 192k), progress queue
  - `backend/app/media/probe.py`: ffprobe validator (1080x1920, 30fps, duration <= 60s, aac), 540x960 thumbnail extractor
  - `backend/app/graph/assembly.py`: Node 3 orchestrator
  - `backend/tests/test_assembly.py`: Render 3 full real videos; test motion liveness, caption sync, and ffprobe stats
- **Verification Command:** `pytest backend/tests/test_assembly.py -v -s`
- **Gate 5:** Review contact sheets, motion liveness, and sample videos. Wait for user confirmation.

---

### Phase 6: Orchestration, Events & API
- **Files to create:**
  - `backend/app/events/public.py`: Strict allow-listed Pydantic event models (`extra="forbid"`)
  - `backend/app/events/messages.py`: Humanized, provider-neutral message catalogue
  - `backend/app/events/sanitizer.py`: Deep leak guard (regex for keys, hostnames, system paths)
  - `backend/app/events/bus.py`: `EventBus` with monotonic sequence persistence
  - `backend/app/events/projection.py`: State fold reconstructing `job.snapshot`
  - `backend/app/graph/state.py` & `backend/app/graph/build.py`: LangGraph StateGraph with conditional entry and tighten loop
  - `backend/app/jobs/runner.py`: `JobRunner` managing concurrency (2), cancellation, retries, and SIGKILL recovery
  - `backend/app/api/jobs.py`: REST routes (`/api/jobs`, cancel, retry, delete) and SSE endpoint (`/events`)
  - `backend/app/api/media.py`: Range-enabled video streaming, thumbnails, scene previews
  - `backend/app/api/health.py`: Health endpoint
  - `backend/app/main.py`: FastAPI app factory, CORS, lifespan startup recovery
  - `backend/tests/test_orchestration.py`: Live job execution via HTTP, SSE reconnect with `Last-Event-ID`, Range 206 test, cancel mid-render test
- **Verification Command:** `pytest backend/tests/test_orchestration.py -v -s`

---

### Phase 7: Frontend Foundation
- **Files to create:**
  - `frontend/package.json`, `next.config.ts`, `tsconfig.json`, `tailwind.config.ts`
  - `frontend/styles/tokens.css` & `frontend/app/globals.css`: Claude-inspired warm paper tones, Newsreader, Inter, Geist Mono typography
  - `frontend/lib/api/schemas.ts`: Strict Zod models matching backend REST contracts
  - `frontend/lib/api/client.ts` & `frontend/lib/api/jobs.ts`: Type-safe HTTP client
  - `frontend/lib/sse/events.ts`: Zod event union
  - `frontend/lib/sse/jobStream.ts`: Resilient SSE client with backoff and `Last-Event-ID` resume
  - `frontend/lib/state/runStore.ts` & `frontend/lib/state/applyEvent.ts`: Zustand + Immer live state reducer
  - `frontend/app/layout.tsx`: Root layout, theme provider, TanStack Query provider, shell layout
  - `frontend/app/page.tsx`: Home composer with inline validation and suggestion chips
- **Verification Command:** `npm --prefix frontend run build && npm --prefix frontend test`

---

### Phase 8: Node Graph & Job Views
- **Files to create:**
  - `frontend/components/graph/PipelineGraph.tsx`: React Flow read-only graph, auto-layout
  - `frontend/components/graph/StageNode.tsx` & `SubNode.tsx`: Animated border pulses, fallback badges, progress bars
  - `frontend/components/graph/FlowEdge.tsx`: Animated dashoffset flow, stage completion packets
  - `frontend/components/job/SceneStrip.tsx`: Real scene thumbnail chips
  - `frontend/components/job/ActivityFeed.tsx`: Humanized chronological event feed
  - `frontend/components/job/ResultPanel.tsx`: 9:16 Video player, download button, metadata
  - `frontend/components/job/FailurePanel.tsx`: Empathetic error panel with stage-specific retry
  - `frontend/app/jobs/[jobId]/page.tsx`: Unified live/result/failure view
- **Verification Command:** E2E Playwright test verifying live graph state changes against running backend.

---

### Phase 9: Library & Polish
- **Files to create:**
  - `frontend/app/library/page.tsx`: Grid with filter tabs (All, Completed, In progress, Failed)
  - `frontend/components/library/JobCard.tsx`: 9:16 thumbnail card, inline play, delete confirm
  - `frontend/components/player/VideoPlayer.tsx`: Custom video controls with keyboard shortcuts (Space, K, Seek)
  - `frontend/lib/copy/errorCopy.ts`: Human-friendly error map
  - Accessibility & CSP hardening
- **Verification Command:** Playwright axe accessibility checks and Lighthouse audit.

---

### Phase 10: Full Test Suite & Final Acceptance (Gate 10 ⛔)
- Complete 20-prompt acceptance corpus testing
- Run `check_no_mocks.sh` and `check_secrets.sh`
- Write comprehensive `README.md` and judge demo guide
- Present Definition-of-Done compliance report
- **Gate 10:** Final review and sign-off.

---

## 4. Key Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Edge-TTS sentence vs word boundary variations | Fallback to sentence proportional timing in `tts.py` |
| MoviePy float rendering shimmer | Sub-pixel float crop box using PIL Lanczos with float coordinates |
| Stock provider rate limits | Token buckets, Pexels-then-Pixabay failover, Query Repair step |
| Windows path & process spawning | Use `multiprocessing.get_context("spawn")` and standard forward/back-slash normalization |
| Secret leakage | Regex scan in sanitizer, pre-commit guard script, `.env` git-ignored |
