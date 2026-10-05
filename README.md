# AutoShorts: Autonomous Multi-Agent Educational Video Generation

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.13-blue.svg?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-Multi--Agent-orange.svg)](https://langchain-ai.github.io/langgraph/)
[![Next.js](https://img.shields.io/badge/Next.js-15%20(App%20Router)-black.svg?logo=next.js&logoColor=white)](https://nextjs.org)
[![FFmpeg](https://img.shields.io/badge/FFmpeg-x264%20CRF%2016-green.svg?logo=ffmpeg&logoColor=white)](https://ffmpeg.org)
[![Zero Mocks](https://img.shields.io/badge/Policy-Zero%20Mocks%20Enforced-critical.svg)](#key-guardrails--zero-mock-policy)
[![License](https://img.shields.io/badge/License-MIT-purple.svg)](LICENSE)

**WCC Launchpad 30 — Agentic AI Track**  
*Transform any educational concept into a fully edited, narrated, subtitled 60-second vertical video (9:16) with zero manual human editing.*

[Features](#features) • [Architecture](#system-architecture) • [Getting Started](#quick-start-guide) • [API & SSE](#rest--sse-api-contract) • [Testing](#verification--test-suite) • [Judge Walkthrough](#judge-demo-walkthrough)

</div>

---

## 🌟 Overview

**AutoShorts** is an autonomous multi-agent media production engine. Given a single topic prompt (e.g. *"Why is the Mariana Trench so deep?"* or *"How do quantum computers factor prime numbers?"*), an ensemble of specialized AI agents collaboratively researches, writes, narrates, sources, edits, and renders a broadcast-quality 60-second vertical video in under 3 minutes.

The companion **Next.js 15** frontend streams the pipeline live via **Server-Sent Events (SSE)**, mapping agent state machines onto an interactive **React Flow** graph with real-time token feeds, audio spectrogram previews, and frame-by-frame progress indicators.

---

## 🚀 Key Features

### 🧠 Autonomous Multi-Agent Pipeline (LangGraph)
- **Research & Script Agent**: Conducts conceptual research and authors a pedagogically structured 5-scene script within a strict 120–140 word budget. Includes automated script-tightening loops if duration targets are exceeded.
- **Parallel Asset Sourcing Agent**: Simultaneously dispatches narration and visual retrieval branches using `asyncio.gather`:
  - **Voice Narration**: Microsoft Edge-TTS with millisecond word boundary timestamps, followed by two-pass EBU R128 (`-16.0 LUFS`) loudnorm audio processing.
  - **Multi-Tier Visual Sourcing**:
    - **AI Image Generation**: Free public Pollinations gateway with sequential multi-model failover (NVIDIA/MIT Sana 4K model $\rightarrow$ default $\rightarrow$ Turbo).
    - **Pexels 9:16 Portrait Video**: Queries curated vertical stock footage with automated physical-noun query sanitization (stripping abstract words and human portraits).
    - **Stock Photography Fallback**: Pexels Photos $\rightarrow$ Pixabay Photos $\rightarrow$ Query Repair.
  - **Multimodal Visual Verifier (Gemini Vision)**: `gemini-3.5-flash-lite` audits candidate visuals against spoken narration and topic concepts in real time, discarding selfies, watermarks, and mismatched footage before rendering.
- **Assembly & Compositing Engine**: Frame-accurate sub-pixel rendering engine combining:
  - **8 Cinematic Motion Presets**: Alternating `PAN_LEFT`, `PAN_RIGHT`, `TILT_UP`, `TILT_DOWN`, `DIAGONAL_PUSH`, `ARC_PAN`, `PUSH_IN`, and `PULL_OUT` evaluated with smooth quintic ease-in-out (`6t⁵ - 15t⁴ + 10t³`) curves.
  - **Picture-in-Picture (PiP) Inset Callouts**: Contextual floating cards with rounded corners, amber borders (`#FED766`), drop shadow, pill badges, and spring pop-in / fade-out animations highlighting comparative metrics and details.
  - **Natural S-Curve Transitions**: Seamless clip blending with `CROSSFADE`, `ZOOM_DISSOLVE`, `SOFT_PUSH`, and `DIP_LIGHT` featuring active velocity glides into transitions (no freeze frames).
  - **Word-Level Pop Captions**: High-DPI Pillow text rasterization with dynamic word-by-word karaoke highlighting, outline strokes, and chapter pill badges.
  - **Studio Master Quality**: Subprocess FFmpeg pipe encoding directly to H.264 CRF 16 with 48 kHz AAC audio, verified via `ffprobe`.

### 🛡️ Uncompromising Reliability & Guardrails
- **100% Real Endpoints (Zero-Mock Policy)**: Zero fake mocks, fixtures, or canned files across the entire codebase. Every agent and test connects to real services.
- **Fail-Closed Complete Audit Logging**: Every single external API request, response, latency metric, and HTTP status code is recorded under `logs/api_calls/<job_id>/` with sanitized credentials and summarized in `logs/runs.jsonl`.
- **Secret Leak Guards**: Automatic regex sanitization strips API keys, local filesystem paths, and hostnames before any event is published over SSE or REST.
- **Player Lock Protection**: The video player is strictly locked during rendering and unlocks automatically with partial HTTP 206 Range seeking upon 100% completion.

---

## 🏗️ System Architecture

```
User Topic Prompt (e.g., "Why is the Mariana Trench so deep?")
  │
  ▼
[FastAPI Backend / JobRunner (Concurrency=2)]
  │
  ├─► Node 1: Research Agent (LangGraph)
  │     └─► LLM Gateway with Sequential Failover
  │           (gemini-2.5-flash → gemini-2.5-flash-lite → backup tiers)
  │           └─► Pedagogical Script (120-140 words, 5-8 scenes, 2-3 visual beats/scene)
  │
  ├─► Node 2: Asset Agent (asyncio.gather parallel branches)
  │     ├─► Voice Branch: Edge-TTS word-timing synthesis + 2-pass Loudnorm (-16.0 LUFS)
  │     └─► Visuals Branch: Multi-Tier Visual Retrieval + Gemini Multimodal Verification
  │           ├─► Tier 1: Pollinations AI Generation (Sana / Default / Turbo)
  │           ├─► Tier 2: Pexels 9:16 Portrait Video (Sanitized Physical Queries)
  │           ├─► Tier 3: Pexels Photos → Pixabay Photos
  │           ├─► Visual Verifier: Gemini 3.5 Flash Lite audits candidate vs. spoken narration
  │           └─► PIL validation, Sobel saliency centroid, perceptual hash de-duplication
  │
  └─► Node 3: Assembly Agent (MoviePy + Subprocess FFmpeg Pipe)
        ├─► TimelineBuilder (word-boundary synchronized shot timing)
        ├─► Motion Engine (Smoothstep Ken Burns, sub-pixel Lanczos, organic drift)
        ├─► Picture-in-Picture (PiP) Inset Callout Overlays (Glassmorphic cards + badges)
        ├─► Natural Transitions (S-curve smoothstep, zoom dissolve, light blooming)
        ├─► High-DPI Pillow Captions (2-4 word animated pop karaoke highlighting)
        ├─► Overlays (Vignette, bottom readability scrim, chapter pill, progress bar)
        ├─► FFmpeg Subprocess (H.264 CRF 16, 48kHz AAC 192k)
        └─► ffprobe verification & 540x960 thumbnail generation
  │
  ▼
Next.js 15 Frontend
  ├─► Real-time SSE Stream (/api/jobs/{id}/events with Last-Event-ID resume)
  ├─► Interactive React Flow Node Graph (active pulses, packets, sub-nodes)
  ├─► Live Humanized Activity Feed (zero internal secrets or raw payloads)
  ├─► Scene Strip & Media Preview
```

---

## 📁 Repository Structure

```
├── backend/
│   ├── app/
│   │   ├── api/             # FastAPI REST endpoints (/api/jobs, /api/media)
│   │   ├── core/            # Config, audit logger, exception handlers
│   │   ├── domain/          # Pydantic domain models (Job, Scene, Timeline, Shot)
│   │   ├── events/          # EventBus, SSE public contracts, payload sanitizer
│   │   ├── gateway/         # Resilient LLM Gateway with sequential failover
│   │   ├── graph/           # LangGraph pipeline nodes (Research, Asset, Assembly)
│   │   ├── jobs/            # SQLite repository with WAL mode & atomic updates
│   │   └── media/           # Timeline builder, motion engine, render worker, text rasterizer
│   ├── tests/               # Real integration & verification tests (Phase 0 to 6)
│   ├── requirements.txt     # Python dependencies
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── app/             # Next.js 15 App Router pages (Home, Job Details, Library)
│   │   ├── components/      # UI components (Graph, Player, ActivityFeed, SceneStrip)
│   │   └── lib/             # Zustand store, SSE client, API wrappers
│   ├── tailwind.config.ts   # Glassmorphic warm dark palette & animations
│   └── package.json
├── docs/                    # Complete product specifications (PRD, Frontend & Backend Specs)
├── logs/                    # Audit logs directory
│   ├── runs.jsonl           # Append-only run registry
│   └── api_calls/           # Per-job detailed audit trails & summary.md
├── scripts/                 # System verification scripts
│   ├── check_no_mocks.py    # Zero-mock scanner
│   ├── check_secrets.py     # Secret leak scanner
│   └── doctor.py            # Environment & dependency readiness verification
└── README.md
```

---

## ⚡ Quick Start Guide

### Prerequisites
- **Python 3.11+**
- **Node.js 18+** & npm
- **FFmpeg & ffprobe** installed and available on `PATH`

### 1. Clone the Repository
```bash
git clone https://github.com/pradnyeshpatil2007/WCC-Launchpad-Hackathon.git
cd WCC-Launchpad-Hackathon
```

### 2. Verify System Readiness & Guardrails
Run the automated system doctor and leak scanners:
```powershell
python scripts/doctor.py
python scripts/check_no_mocks.py
python scripts/check_secrets.py
```

### 3. Backend Setup
Configure your API keys in `backend/.env`:
```ini
GEMINI_API_KEY=your_gemini_api_key
PEXELS_API_KEY=your_pexels_api_key
PIXABAY_API_KEY=your_pixabay_api_key
PORT=8000
STORAGE_DIR=../storage
LOGS_DIR=../logs
```

Install dependencies and start the backend:
```powershell
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```
*The backend automatically performs live startup preflight checks against Gemini and stock providers.*

### 4. Frontend Setup
In a separate terminal:
```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000` in your browser.

---

## 📡 REST & SSE API Contract

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/jobs` | Submit a prompt to start video generation (`{"prompt": "..."}`) |
| `GET` | `/api/jobs` | List recent video generation jobs |
| `GET` | `/api/jobs/{id}` | Retrieve job state, stage, progress, and metadata |
| `GET` | `/api/jobs/{id}/events` | Real-time SSE stream with `Last-Event-ID` auto-reconnect |
| `DELETE` | `/api/jobs/{id}` | Cancel/delete job and purge disk assets |
| `GET` | `/api/media/{id}/{file}` | Stream video (`HTTP 206 Partial Content`) or download assets |

### Public SSE Event Types
- `stage.started` / `stage.completed`: Top-level node state changes (`research`, `asset`, `assembly`).
- `substep.progress`: Fine-grained frame-by-frame rendering percentage, FPS, and ETA.
- `scene.voice_ready` / `scene.visual_ready`: Per-scene asset completion indicators.
- `job.completed` / `job.failed`: Terminal states with final video URLs or error details.

---

## 🧪 Verification & Test Suite

AutoShorts contains real live verification tests exercising every phase without mocks:

```powershell
# Phase 0 & 1: Audit logging, secret masking, fail-closed enforcement
pytest backend/tests/test_audit_log.py -v -s

# Phase 2: LLM Gateway 5-model failover & recovery
pytest backend/tests/test_gateway.py -v -s

# Phase 3: Research Agent word-budget adherence & script schemas
pytest backend/tests/test_research.py -v -s

# Phase 4: Parallel voice & visual asset sourcing
pytest backend/tests/test_asset.py -v -s

# Phase 5: Assembly engine, 1080x1920 render, and ffprobe verification
pytest backend/tests/test_assembly.py -v -s

# Phase 6: REST API, SSE replay, HTTP Range 206 seeking, job lifecycle
pytest backend/tests/test_api_and_pipeline.py -v -s
```

Frontend production build check:
```powershell
cd frontend && npm run build
```

---

## 🏆 Judge Demo Walkthrough

1. **Submit Topic**: On the homepage (`http://localhost:3000`), choose an educational topic or click one of the pre-loaded topic chips (e.g., *"Why do neutron stars spin so fast?"*).
2. **Real-Time Agency Visualization**:
   - The UI transitions instantly to `/jobs/<id>`.
   - Observe the **React Flow** graph illuminate nodes as agents execute.
   - Watch the parallel sub-nodes split between narration synthesis and visual generation.
   - Review the clean **Activity Feed** logging humanized progress without exposing secrets or paths.
3. **Smooth Progress Tracking**:
   - Watch the golden gradient progress bar advance continuously across all sub-steps and frame rendering.
4. **Playback Lock & Reveal**:
   - Notice the player is securely locked during generation with a badge: `Generating video (player unlocks on completion)`.
   - Upon completion (100%), the view automatically unlocks the full 9:16 player.
5. **Inspect the Master Video**:
   - Play the 1080x1920 vertical video with synchronized word-by-word karaoke captions, smooth Ken Burns camera motions, and organic scene transitions.
6. **Audit Transparency**:
   - Open `logs/runs.jsonl` or `logs/api_calls/<job_id>/summary.md` to inspect the exact external API calls, HTTP status codes, latency, and fallback paths used.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE). Built for the **WCC Launchpad 30 Hackathon (Agentic AI Track)**.
