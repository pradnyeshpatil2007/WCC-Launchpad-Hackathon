# External API & Library Verification Record

This document records the results of live probes and verification checks against external services and libraries before depending on them, as mandated by Document 3 §21.

---

## 1. Gemini Model Identifiers & Availability
- **Specification:** `gemini-3.5-flash`, `gemini-3.5-flash-lite`, `gemini-3.6-flash`, `gemini-3.7-flash`, `gemini-3.8-flash`.
- **Preflight probe:** `GET https://generativelanguage.googleapis.com/v1beta/models/{model}` with `x-goog-api-key`.
- **Status:** Pending Gate 0 key configuration.
- **Probe Results:**
  - *To be recorded during Phase 1 preflight.*

---

## 2. Image Generation API (Pollinations.ai Flux)
- **Specification:** GET `https://gen.pollinations.ai/image/{prompt}?width=1080&height=1920&model=flux&nologo=true`
- **Output:** Binary image (JPEG/PNG) in 9:16 aspect ratio (1080x1920).
- **Fallback:** Pexels then Pixabay.
- **Probe Results:**
  - *To be recorded in Phase 4.*

---

## 3. Gemini Structured JSON Schema
- **Specification:** `responseMimeType: "application/json"`, `responseJsonSchema` or `responseSchema`.
- **Notes:** Inlining `$defs`, stripping unsupported JSON schema fields while enforcing via Pydantic v2.
- **Probe Results:**
  - *To be recorded in Phase 2.*

---

## 4. Edge-TTS Boundary Behavior
- **Specification:** `edge_tts.Communicate(..., boundary="WordBoundary")`.
- **Units:** 100-nanosecond ticks to seconds (`offset / 10_000_000.0`).
- **Fallback:** Sentence boundary proportional distribution if word boundaries are absent.
- **Probe Results:**
  - *To be recorded in Phase 1 / Phase 4.*

---

## 5. MoviePy 2.x API & FFmpeg Parameters
- **Specification:** MoviePy 2.x `VideoClip(make_frame, duration)`, float sub-pixel crop box with Pillow Lanczos, x264 `preset=slow`, `crf=16`, AAC audio.
- **Probe Results:**
  - *To be recorded in Phase 5.*

---

## 6. Stock Providers (Pexels & Pixabay)
- **Pexels:** `GET https://api.pexels.com/v1/search?query={q}&orientation=portrait&size=large&per_page={N}&page=1`, Header: `Authorization: <key>`.
- **Pixabay:** `GET https://pixabay.com/api/?key={key}&q={q}&image_type=photo&orientation=vertical&min_width=720&min_height=1280&safesearch=true&order=popular&per_page={N}`.
- **Probe Results:**
  - *To be recorded during Phase 1 preflight.*

---

## 7. Starlette FileResponse HTTP Range Support
- **Specification:** Range header support (`Range: bytes=0-1023`) returning HTTP 206 Partial Content.
- **Probe Results:**
  - *To be recorded in Phase 6.*
