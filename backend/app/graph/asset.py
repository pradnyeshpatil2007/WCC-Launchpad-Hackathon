"""Node 2: Asset Agent executing concurrent Voice (TTS) and Visuals acquisition (Doc 3 §12)."""

import asyncio
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from PIL import Image

from app.config import get_settings
from app.core.errors import StageError
from app.core.http_client import LoggedHttpClient
from app.core.storage import atomic_write_bytes, atomic_write_json, get_job_storage_dir
from app.domain.assets import (
    AcceptedImage,
    SceneAudio,
    SceneVisuals,
    VisualManifest,
    VoiceManifest,
    WordTiming,
)
from app.domain.script import Script
from app.llm.gateway import LLMGateway
from app.llm.gemini_rest import Content, ContentPart, LLMRequest
from app.media.audio import assemble_narration_audio, convert_and_trim_audio
from app.media.imaging import evaluate_and_process_image, generate_preview
from app.providers.image_gen import PollinationsImageGen
from app.providers.stock import UnifiedStockService
from app.providers.tts import LoggedEdgeTTS


class AssetAgent:
    def __init__(
        self,
        http_client: Optional[LoggedHttpClient] = None,
        gateway: Optional[LLMGateway] = None,
    ):
        self.settings = get_settings()
        self.http_client = http_client or LoggedHttpClient()
        self.gateway = gateway or LLMGateway(self.http_client)
        self.image_gen = PollinationsImageGen(self.http_client)
        self.stock_service = UnifiedStockService(self.http_client)
        self._tts_semaphore = asyncio.Semaphore(self.settings.TTS_CONCURRENCY)
        self._img_semaphore = asyncio.Semaphore(self.settings.IMAGE_GEN_CONCURRENCY)

    async def execute(
        self,
        script: Script,
        job_id: str = "_system",
        event_cb: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        force_image_failure: bool = False,
        force_stock_failure: bool = False,
    ) -> Tuple[VoiceManifest, VisualManifest]:
        """Execute concurrent Voice and Visual acquisition via asyncio.gather."""
        storage_dir = get_job_storage_dir(job_id)

        # Notify start of parallel sub-nodes
        if event_cb:
            event_cb("substep.started", {"node": "asset.voice", "message": "Synthesizing narration with Edge-TTS"})
            event_cb("substep.started", {"node": "asset.visuals", "message": "Acquiring 9:16 portrait visuals"})

        # Concurrently gather Voice and Visuals
        voice_task = self.run_voice(script, job_id, storage_dir, event_cb)
        visual_task = self.run_visuals(
            script, job_id, storage_dir, event_cb,
            force_image_failure=force_image_failure,
            force_stock_failure=force_stock_failure,
        )

        results = await asyncio.gather(voice_task, visual_task, return_exceptions=True)

        voice_res, visual_res = results[0], results[1]

        # Handle exceptions from gather
        if isinstance(voice_res, Exception):
            if event_cb:
                event_cb("substep.completed", {"node": "asset.voice", "durationMs": 0})
            raise voice_res

        if isinstance(visual_res, Exception):
            if event_cb:
                event_cb("substep.completed", {"node": "asset.visuals", "durationMs": 0})
            raise visual_res

        if event_cb:
            event_cb("substep.completed", {"node": "asset.voice", "durationMs": 0})
            event_cb("substep.completed", {"node": "asset.visuals", "durationMs": 0})

        return voice_res, visual_res

    # --- VOICE BRANCH ---

    async def run_voice(
        self,
        script: Script,
        job_id: str,
        storage_dir: Path,
        event_cb: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    ) -> VoiceManifest:
        """Synthesize audio per scene, check budget, apply rate bump if needed, and normalize."""
        tts = LoggedEdgeTTS(job_id=job_id)
        audio_dir = storage_dir / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)

        rate_bump = 0
        current_rate = self.settings.TTS_RATE

        async def synth_scene(idx: int, scene_text: str, rate: str) -> Tuple[Path, float, List[WordTiming], str]:
            async with self._tts_semaphore:
                raw_audio, raw_timings, mode = await tts.synthesize(
                    text=scene_text,
                    rate=rate,
                    label=f"scene_{idx:02d}",
                )
                mp3_path = audio_dir / f"scene_{idx:02d}.mp3"
                wav_path = audio_dir / f"scene_{idx:02d}.wav"
                atomic_write_bytes(mp3_path, raw_audio)

                duration, word_timings = await convert_and_trim_audio(
                    input_mp3_path=mp3_path,
                    output_wav_path=wav_path,
                    raw_word_timings=raw_timings,
                )
                return wav_path, duration, word_timings, mode

        # First synthesis pass
        tasks = [synth_scene(i, s.narration, current_rate) for i, s in enumerate(script.scenes)]
        synth_results = await asyncio.gather(*tasks)

        scene_wavs: List[Path] = [r[0] for r in synth_results]
        scene_durations: List[float] = [r[1] for r in synth_results]
        scene_timings: List[List[WordTiming]] = [r[2] for r in synth_results]
        scene_modes: List[str] = [r[3] for r in synth_results]

        lead_in = self.settings.VIDEO_LEAD_IN_SECONDS
        tail = self.settings.VIDEO_TAIL_SECONDS
        gap = 0.12
        total_time = lead_in + sum(scene_durations) + gap * (len(script.scenes) - 1) + tail

        # Budget check: require total <= VIDEO_MAX_SECONDS - 0.5 (59.5s)
        max_allowed = self.settings.VIDEO_MAX_SECONDS - 0.5
        if total_time > max_allowed:
            # Attempt rate bumps: +4%, +8%, +12%, up to TTS_MAX_RATE_BUMP_PERCENT
            bump_candidates = sorted(set([4, 8, 12, self.settings.TTS_MAX_RATE_BUMP_PERCENT]))
            for bump in bump_candidates:
                bump_rate = f"+{bump}%"
                re_tasks = [synth_scene(i, s.narration, bump_rate) for i, s in enumerate(script.scenes)]
                re_results = await asyncio.gather(*re_tasks)
                re_durations = [r[1] for r in re_results]
                re_total = lead_in + sum(re_durations) + gap * (len(script.scenes) - 1) + tail
                total_time = re_total
                if re_total <= max_allowed:
                    rate_bump = bump
                    current_rate = bump_rate
                    scene_wavs = [r[0] for r in re_results]
                    scene_durations = re_durations
                    scene_timings = [r[2] for r in re_results]
                    scene_modes = [r[3] for r in re_results]
                    break

        if total_time > max_allowed:
            raise StageError(
                code="AUDIO_OVER_BUDGET",
                stage="asset",
                message=f"Total narration duration ({total_time:.1f}s) exceeds maximum 60s limit",
                retryable=True,
            )

        # Assemble normalized narration.wav
        narration_wav = audio_dir / "narration.wav"
        final_duration = await assemble_narration_audio(
            scene_wav_paths=scene_wavs,
            output_narration_path=narration_wav,
            lead_in=lead_in,
            gap_duration=gap,
            tail=tail,
            target_lufs=self.settings.VIDEO_LOUDNESS_LUFS,
        )

        scenes_audio = []
        for i in range(len(script.scenes)):
            scenes_audio.append(
                SceneAudio(
                    scene_index=i,
                    file=str(scene_wavs[i].relative_to(storage_dir)),
                    duration_sec=round(scene_durations[i], 3),
                    words=scene_timings[i],
                    timing_mode=scene_modes[i],  # type: ignore
                    voice=self.settings.TTS_VOICE,
                    rate=current_rate,
                )
            )
            if event_cb:
                event_cb("scene.voice_ready", {"sceneIndex": i, "durationSec": round(scene_durations[i], 3)})

        voice_manifest = VoiceManifest(
            scenes=scenes_audio,
            total_sec=round(final_duration, 3),
            rate_bump_percent=rate_bump,
        )

        # Persist stage artifact
        stages_dir = storage_dir / "stages"
        stages_dir.mkdir(parents=True, exist_ok=True)
        atomic_write_json(stages_dir / "voice.json", voice_manifest.model_dump())

        return voice_manifest

    # --- VISUALS BRANCH ---

    async def run_visuals(
        self,
        script: Script,
        job_id: str,
        storage_dir: Path,
        event_cb: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        force_image_failure: bool = False,
        force_stock_failure: bool = False,
    ) -> VisualManifest:
        """Acquire visuals per beat with fallback to stock, Query Repair, and scene top-up."""
        images_dir = storage_dir / "images"
        previews_dir = storage_dir / "previews"
        images_dir.mkdir(parents=True, exist_ok=True)
        previews_dir.mkdir(parents=True, exist_ok=True)

        existing_phashes: List[str] = []
        seen_stock_ids: Set[str] = set()
        credits_list: List[Dict[str, Any]] = []
        scenes_visuals: List[SceneVisuals] = []

        for s_idx, scene in enumerate(script.scenes):
            scene_accepted_images: List[AcceptedImage] = []

            for b_idx, beat in enumerate(scene.beats):
                beat_key = f"s{s_idx:02d}_b{b_idx:02d}"
                accepted_img: Optional[AcceptedImage] = None

                # 1. Primary: AI Image Generation (Pollinations.ai Flux)
                if not force_image_failure:
                    async with self._img_semaphore:
                        gen_bytes = await self.image_gen.generate_image(
                            prompt=beat.image_prompt,
                            job_id=job_id,
                            beat_key=beat_key,
                            attempt=1,
                        )
                        if gen_bytes:
                            eval_res = evaluate_and_process_image(
                                raw_bytes=gen_bytes,
                                source="generated",
                                existing_phashes=existing_phashes,
                            )
                            if eval_res.accepted and eval_res.image is not None:
                                img_filename = f"{beat_key}.jpg"
                                img_path = images_dir / img_filename
                                eval_res.image.save(img_path, "JPEG", quality=92)
                                existing_phashes.append(eval_res.phash)

                                # Create 270x480 preview
                                prev_path = previews_dir / f"s{s_idx:02d}.jpg"
                                generate_preview(eval_res.image, prev_path)

                                accepted_img = AcceptedImage(
                                    beat_key=beat_key,
                                    file=str(img_path.relative_to(storage_dir)),
                                    width=eval_res.image.width,
                                    height=eval_res.image.height,
                                    source="generated",
                                    source_ref={"model": "pollinations-flux"},
                                    focal=eval_res.focal,
                                    phash=eval_res.phash,
                                    preview_file=str(prev_path.relative_to(storage_dir)),
                                )

                # 2. Fallback to Stock (Pexels -> Pixabay)
                if accepted_img is None and not force_stock_failure:
                    if event_cb:
                        event_cb(
                            "fallback.used",
                            {
                                "node": "asset.visuals",
                                "sceneIndex": s_idx,
                                "kind": "visual_source",
                                "message": f"Using curated stock imagery for scene {s_idx + 1}",
                            },
                        )

                    stock_res = await self.stock_service.search_and_download_candidate(
                        queries=beat.stock_queries,
                        job_id=job_id,
                        beat_key=beat_key,
                        existing_phashes=existing_phashes,
                        seen_stock_ids=seen_stock_ids,
                    )

                    # 3. Query Repair if stock search returned nothing
                    if stock_res is None:
                        repair_queries = await self._query_repair(beat.stock_queries, scene.emphasis_text, job_id)
                        stock_res = await self.stock_service.search_and_download_candidate(
                            queries=repair_queries,
                            job_id=job_id,
                            beat_key=beat_key,
                            existing_phashes=existing_phashes,
                            seen_stock_ids=seen_stock_ids,
                        )

                    if stock_res is not None:
                        raw_bytes, cand_meta, eval_res = stock_res
                        img_filename = f"{beat_key}.jpg"
                        img_path = images_dir / img_filename
                        eval_res.image.save(img_path, "JPEG", quality=92)
                        existing_phashes.append(eval_res.phash)

                        prev_path = previews_dir / f"s{s_idx:02d}.jpg"
                        generate_preview(eval_res.image, prev_path)

                        credits_list.append(cand_meta)
                        accepted_img = AcceptedImage(
                            beat_key=beat_key,
                            file=str(img_path.relative_to(storage_dir)),
                            width=eval_res.image.width,
                            height=eval_res.image.height,
                            source=cand_meta["provider"],
                            source_ref=cand_meta,
                            focal=eval_res.focal,
                            phash=eval_res.phash,
                            preview_file=str(prev_path.relative_to(storage_dir)),
                        )

                if accepted_img is not None:
                    scene_accepted_images.append(accepted_img)

            # Scene Top-up check
            # Target 2-5 images per scene (never below 1)
            target_images = max(2, min(5, len(scene.beats)))
            if len(scene_accepted_images) < target_images and not force_stock_failure:
                topup_queries = [scene.emphasis_text.lower(), script.title.lower()]
                topup_res = await self.stock_service.search_and_download_candidate(
                    queries=topup_queries,
                    job_id=job_id,
                    beat_key=f"s{s_idx:02d}_topup",
                    existing_phashes=existing_phashes,
                    seen_stock_ids=seen_stock_ids,
                )
                if topup_res is not None:
                    raw_bytes, cand_meta, eval_res = topup_res
                    topup_path = images_dir / f"s{s_idx:02d}_bonus.jpg"
                    eval_res.image.save(topup_path, "JPEG", quality=92)
                    existing_phashes.append(eval_res.phash)
                    credits_list.append(cand_meta)
                    scene_accepted_images.append(
                        AcceptedImage(
                            beat_key=f"s{s_idx:02d}_bonus",
                            file=str(topup_path.relative_to(storage_dir)),
                            width=eval_res.image.width,
                            height=eval_res.image.height,
                            source=cand_meta["provider"],
                            source_ref=cand_meta,
                            focal=eval_res.focal,
                            phash=eval_res.phash,
                        )
                    )

            # Strict no-mock check: if a scene has 0 real images, FAIL
            if len(scene_accepted_images) == 0:
                raise StageError(
                    code="VISUALS_UNAVAILABLE",
                    stage="asset",
                    message=f"Could not find valid visual images for scene {s_idx + 1}",
                    retryable=True,
                )

            scenes_visuals.append(
                SceneVisuals(
                    scene_index=s_idx,
                    images=scene_accepted_images,
                )
            )

            if event_cb:
                primary_source = scene_accepted_images[0].source
                event_cb(
                    "scene.visual_ready",
                    {
                        "sceneIndex": s_idx,
                        "source": primary_source,
                        "imageCount": len(scene_accepted_images),
                        "previewUrl": f"/api/media/{job_id}/scenes/{s_idx}/preview",
                    },
                )

        visual_manifest = VisualManifest(scenes=scenes_visuals)

        # Persist stage artifacts
        stages_dir = storage_dir / "stages"
        stages_dir.mkdir(parents=True, exist_ok=True)
        atomic_write_json(stages_dir / "visuals.json", visual_manifest.model_dump())
        atomic_write_json(storage_dir / "credits.json", credits_list)

        return visual_manifest

    async def _query_repair(self, failed_queries: List[str], emphasis_text: str, job_id: str) -> List[str]:
        """Ask LLM Gateway to generate 6 broader, concrete stock search keywords."""
        prompt = (
            f"The following stock photo search queries returned 0 results: {failed_queries}.\n"
            f"Scene emphasis text: '{emphasis_text}'.\n"
            f"Please output 6 concrete, simple, photographic stock photo search keywords (1-3 words each), separated by commas."
        )
        req = LLMRequest(
            purpose="keyword_repair",
            contents=[Content(parts=[ContentPart(text=prompt)])],
            temperature=0.3,
            job_id=job_id,
        )
        try:
            res = await self.gateway.generate(req)
            terms = [t.strip().lower() for t in res.text.split(",") if t.strip()]
            return terms[:6]
        except Exception:
            words = [w for w in re.findall(r"\w+", emphasis_text.lower()) if len(w) >= 3]
            return words[:4] if words else [emphasis_text.lower()]
