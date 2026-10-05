# AutoShorts: Autonomous Multi-Agent Educational Video Generation

> **WCC Launchpad 30 — Agentic AI Track**  
> Turn any educational concept into a polished, narrated, animated 60-second vertical video (9:16) with zero manual human editing.

---

## 1. System Architecture

```
User Topic Prompt (3-500 chars)
  │
  ▼
[FastAPI Backend / JobRunner (Concurrency=2)]
  │
  ├─► Node 1: Research Agent (LangGraph)
  │     └─► LLM Gateway with Sequential Failover
  │           (gemini-3.5-flash → lite → 3.6 → 3.7 → 3.8)
  │           └─► Pedagogical Script (120-140 words, 5-8 scenes, 2-3 visual beats/scene)
  │
  ├─► Node 2: Asset Agent (asyncio.gather parallel branches)
  │     ├─► Voice Branch: Edge-TTS word-timing synthesis + 2-pass Loudnorm (-16.0 LUFS)
  │     └─► Visuals Branch: Pollinations.ai Flux (9:16) → Pexels → Pixabay → Query Repair
  │           └─► PIL validation, Sobel saliency centroid, perceptual hash de-duplication
  │
  └─► Node 3: Assembly Agent (MoviePy + Subprocess FFmpeg Pipe)
        ├─► TimelineBuilder (word-boundary synchronized shot timing)
        ├─► Motion Engine (Smoothstep Ken Burns, sub-pixel Lanczos, organic handheld drift)
        ├─► High-DPI Pillow Captions (2-4 word animated pop karaoke highlighting)
        ├─► Overlays (Vignette, bottom readability scrim, emphasis badges, progress bar)
        ├─► FFmpeg Subprocess (H.264 CRF 16, 48kHz AAC 192k)
        └─► ffprobe verification & 540x960 thumbnail generation
  │
  ▼
Next.js 15 Frontend
  ├─► Real-time SSE Stream (/api/jobs/{id}/events with Last-Event-ID resume)
  ├─► Interactive React Flow Node Graph (active pulses, packets, sub-nodes)
  ├─► Live Humanized Activity Feed (zero internal secrets or raw payloads)
  ├─► Scene Strip & Media Preview
  └─► Video Library & 9:16 Player (HTTP Range 206 seeking & MP4 download)
```

---

## 2. Key Guardrails & Non-Negotiable Rules

1. **NO MOCK DATA**: Zero `unittest.mock`, `pytest-mock`, `msw`, `faker`, or canned fixtures. Every test and workflow exercises real endpoints.
2. **COMPLETE AUDIT LOGGING**: Every outbound HTTP/TTS call is captured under `logs/api_calls/<job_id>/` with `request.json`, `response.json`, `meta.json`, externalized binaries, and redacted API keys.
3. **SECRETS LEAK GUARD**: `NEXT_PUBLIC_API_BASE_URL` is the only frontend env variable. Outbound SSE and REST payloads are validated by a deep regex sanitizer that strips keys, hostnames, and local paths.
4. **FAIL-CLOSED AUDITING**: If audit log writing fails under `LOG_FAIL_CLOSED=true`, the call safely aborts with `AUDIT_LOG_FAILURE`.

---

## 3. Quick Start Guide

### Prerequisites
- Python 3.11+
- Node.js 18+ & npm
- FFmpeg and ffprobe installed and available on `PATH`

### 1. Run System Doctor & Readiness Check
Verify all system dependencies, fonts, FFmpeg, and directories:
```powershell
python scripts/doctor.py
```

### 2. Verify Guardrails & Leak Guards
Ensure zero mocks and zero exposed secrets in the repository:
```powershell
python scripts/check_no_mocks.py
python scripts/check_secrets.py
```

### 3. Backend Setup & Startup
Configure API keys in `backend/.env`:
```ini
GEMINI_API_KEY=your_gemini_api_key
PEXELS_API_KEY=your_pexels_api_key
PIXABAY_API_KEY=your_pixabay_api_key
```

Run database initialization and start the FastAPI dev server:
```powershell
# From backend directory:
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
The backend automatically executes live preflight checks on startup, validating Gemini models, stock providers, and Edge-TTS connectivity.

### 4. Frontend Setup & Startup
```powershell
# From frontend directory:
npm run dev
```
Open `http://localhost:3000` to interact with the application.

---

## 4. Verification & Test Suite

AutoShorts contains real live verification tests across all phases:

| Phase | Test File | Description |
|---|---|---|
| **Phase 0 & 1** | `test_audit_log.py` | Live preflight probes, audit tree logging, secret masking, fail-closed enforcement |
| **Phase 2** | `test_gateway.py` | 5-model sequential failover, real 404 recovery, exhaustion handling, auth validation |
| **Phase 3** | `test_research.py` | 5 diverse topics, strict 120-140 word budget, schema validation, tighten feedback |
| **Phase 4** | `test_asset.py` | Live parallel TTS & image sourcing, stock fallback, impossible query defense |
| **Phase 5** | `test_assembly.py` | Full 1080x1920 video render, ffprobe quality checks, 540x960 thumbnail, contact sheet |
| **Phase 6** | `test_api_and_pipeline.py` | REST API, SSE streaming replay, HTTP Range 206 seeking, job cancellation |

Run all tests:
```powershell
pytest backend/tests/test_audit_log.py -v -s
pytest backend/tests/test_gateway.py -v -s
pytest backend/tests/test_api_and_pipeline.py -v -s
pytest backend/tests/test_research.py -v -s
pytest backend/tests/test_assembly.py -v -s
```

Frontend build validation:
```powershell
npm --prefix frontend run build
```

---

## 5. Judge Demo Walkthrough

1. **Launch**: Open `http://localhost:3000`. Notice the warm dark aesthetic with glassmorphism panels.
2. **Submit Topic**: Click one of the example chips (e.g. *"Why do neutron stars spin so fast?"*) or type your own concept and hit Enter.
3. **Watch Agency Live**:
   - The UI immediately transitions to `/jobs/<id>` in under 300ms.
   - Watch the animated React Flow node graph highlight nodes in real-time as SSE events stream in.
   - Observe parallel sub-nodes for Voice Narration and Visual Sourcing updating concurrently.
   - Inspect the humanized Activity Feed displaying real-time progress without leaking system secrets.
4. **Inspect Generated Video**:
   - Review the completed 9:16 vertical video in the custom player with full seeking (HTTP Range 206 partial content delivery).
   - Check the synchronized animated pop captions with yellow highlighting and smooth Ken Burns motion.
   - Download the high-definition MP4.
5. **Explore Library**: Navigate to `/library` to see all previously rendered projects, filter by status, replay, or delete.
6. **Verify Transparency**: Open `logs/api_calls/<job_id>/` to inspect the complete audit log, request/response headers, and timing metrics for every single external API call.
