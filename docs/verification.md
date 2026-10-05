# External API & Library Verification Record

This document records the results of live probes and verification checks against external services and libraries before depending on them, as mandated by Document 3 §21.

---

## 1. Gemini Model Identifiers & Availability
- **Specification:** `gemini-3.5-flash`, `gemini-3.5-flash-lite`, `gemini-3.6-flash`, `gemini-3.7-flash`, `gemini-3.8-flash`.
- **Preflight probe:** `GET https://generativelanguage.googleapis.com/v1beta/models/{model}` with `x-goog-api-key`.
- **Status:** Verified Live in Phase 1 (Startup Preflight).
- **Probe Results:**
  - `gemini-3.5-flash`: HTTP 200 OK (available)
  - `gemini-3.5-flash-lite`: HTTP 200 OK (available)
  - `gemini-3.6-flash`: HTTP 200 OK (available)
  - `gemini-3.7-flash`: HTTP 200 OK (available)
  - `gemini-3.8-flash`: HTTP 200 OK (available)
  All 5 models in the sequence are active and reachable on the configured key.

---

## 2. Image Generation API (Pollinations.ai Flux)
- **Specification:** GET `https://gen.pollinations.ai/image/{prompt}?width=1080&height=1920&model=flux&nologo=true`
- **Output:** Binary image (JPEG/PNG) in 9:16 aspect ratio (1080x1920).
- **Fallback:** Pexels then Pixabay.
- **Probe Results:**
  - Live probe completed: Pollinations Flux endpoint active and responsive.
  - Successfully retrieved 1080x1920 vertical frames; Sobel focal point and perceptual hash (dHash/pHash) validated without duplicates.
  - Fallback sequence verified: Forced image failure smoothly falls back to Pexels and Pixabay with query repair.

---

## 3. Gemini Structured JSON Schema
- **Specification:** `responseMimeType: "application/json"`, `responseJsonSchema` or `responseSchema`.
- **Notes:** Inlining `$defs`, stripping unsupported JSON schema fields while enforcing via Pydantic v2.
- **Probe Results:**
  - Verified Live in Phase 2 & Phase 3.
  - Script Pydantic models validated across diverse topics: 5-8 scenes, 2-3 visual beats/scene, strict 120-140 total spoken words.
  - Tighten feedback loop verified: word budget reduced by 8-10 words on constraint feedback.

---

## 4. Edge-TTS Boundary Behavior
- **Specification:** `edge_tts.Communicate(..., boundary="WordBoundary")`.
- **Units:** 100-nanosecond ticks to seconds (`offset / 10_000_000.0`).
- **Fallback:** Sentence boundary proportional distribution if word boundaries are absent.
- **Probe Results:**
  - Verified live: Synthesized test phrase, captured boundary events and raw audio in `logs/api_calls/_system/`.
  - Mode: `word_boundary` active and verified.
  - FFmpeg two-pass `loudnorm` filter normalized to target -16.0 LUFS.

---

## 5. MoviePy 2.x API & FFmpeg Parameters
- **Specification:** MoviePy 2.x `VideoClip(make_frame, duration)`, float sub-pixel crop box with Pillow Lanczos, x264 `preset=slow`/`fast`, `crf=16`, AAC audio.
- **Probe Results:**
  - Verified Live in Phase 5.
  - Rendered complete 1080x1920 H.264 video with AAC 192k audio.
  - Output verified by `ffprobe`: 1080x1920 resolution, 30.0 fps, duration <= 60.0s, high profile.
  - High-DPI 540x960 thumbnail and 12-frame contact sheet generated and verified.

---

## 6. Stock Providers (Pexels & Pixabay)
- **Pexels:** `GET https://api.pexels.com/v1/search?query={q}&orientation=portrait&size=large&per_page={N}&page=1`, Header: `Authorization: <key>`.
- **Pixabay:** `GET https://pixabay.com/api/?key={key}&q={q}&image_type=photo&orientation=vertical&min_width=720&min_height=1280&safesearch=true&order=popular&per_page={N}`.
- **Probe Results:**
  - Pexels: HTTP 200 OK verified on `/v1/search?query=nature&per_page=1`.
  - Pixabay: HTTP 200 OK verified on `/api/?q=nature&per_page=3`.

---

## 7. Starlette FileResponse HTTP Range Support
- **Specification:** Range header support (`Range: bytes=0-1023`) returning HTTP 206 Partial Content.
- **Probe Results:**
  - Verified Live in Phase 6 (`test_media_http_range_support`).
  - Request with `Range: bytes=0-999` returned HTTP 206 Partial Content with `Content-Range: bytes 0-999/<total>` and `Accept-Ranges: bytes`.
