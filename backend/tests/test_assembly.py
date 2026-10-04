"""Live end-to-end tests for Phase 5 Assembly Agent and Media Engine."""

import json
from pathlib import Path
import pytest
from PIL import Image

from app.domain.assets import VisualManifest, VoiceManifest
from app.domain.script import Script
from app.graph.assembly import AssemblyAgent
from app.media.probe import probe_video_streams, verify_video_quality
from tests.test_asset import sample_script


@pytest.mark.asyncio
async def test_assembly_end_to_end_render(sample_script):
    """Full live test of AssemblyAgent: renders real video with FFmpeg, verifies probe and contact sheet."""
    job_id = "test_asset_stock_fallback"
    agent = AssemblyAgent()
    storage_dir = agent.settings.resolved_media_dir / "jobs" / job_id

    voice_path = storage_dir / "stages" / "voice.json"
    visuals_path = storage_dir / "stages" / "visuals.json"
    assert voice_path.exists(), "voice.json must exist from Phase 4"
    assert visuals_path.exists(), "visuals.json must exist from Phase 4"

    voice = VoiceManifest.model_validate_json(voice_path.read_text(encoding="utf-8"))
    visuals = VisualManifest.model_validate_json(visuals_path.read_text(encoding="utf-8"))

    events = []
    def event_cb(ev_type, payload):
        events.append((ev_type, payload))

    # Run assembly
    assembly_job_id = "test_assembly_live"
    assembly_storage = agent.settings.resolved_media_dir / "jobs" / assembly_job_id
    assembly_storage.mkdir(parents=True, exist_ok=True)

    # Copy input audio and images to assembly job storage
    import shutil
    shutil.copytree(storage_dir / "audio", assembly_storage / "audio", dirs_exist_ok=True)
    shutil.copytree(storage_dir / "images", assembly_storage / "images", dirs_exist_ok=True)

    result = await agent.execute(
        script=sample_script,
        voice=voice,
        visuals=visuals,
        job_id=assembly_job_id,
        event_cb=event_cb,
    )

    # 1. Verify assembly result
    video_path = assembly_storage / "video.mp4"
    thumb_path = assembly_storage / "thumbnail.jpg"
    assert video_path.exists()
    assert thumb_path.exists()

    # 2. Verify ffprobe quality checks
    probe = verify_video_quality(video_path)
    assert probe["width"] == 1080
    assert probe["height"] == 1920
    assert probe["video_codec"] in ("h264", "libx264")
    assert probe["audio_codec"] == "aac"
    assert 0 < probe["duration_sec"] <= 60.0
    assert probe["file_size_kb"] > 500.0
    print(f"\n[+] Video ffprobe verified: {probe['width']}x{probe['height']}, {probe['duration_sec']:.2f}s, {probe['file_size_kb']:.1f} KB")

    # 3. Verify thumbnail dimensions (540x960)
    with Image.open(thumb_path) as thumb_img:
        assert thumb_img.size == (540, 960)
        print(f"[+] Thumbnail verified: {thumb_img.size[0]}x{thumb_img.size[1]}")

    # 4. Verify event sequence
    event_types = [e[0] for e in events]
    assert "substep.started" in event_types
    assert "substep.progress" in event_types
    assert "substep.completed" in event_types
    assert "media.video_ready" in event_types

    # 5. Extract 12 representative frames for contact sheet verification
    verification_dir = agent.settings.resolved_media_dir / "verification"
    verification_dir.mkdir(parents=True, exist_ok=True)
    contact_sheet_path = verification_dir / "contact_sheet.jpg"

    timestamps = [2.0, 6.0, 11.0, 16.0, 21.0, 26.0, 31.0, 36.0, 41.0, 46.0, 51.0, 56.0]
    frame_images = []

    import subprocess
    for idx, ts in enumerate(timestamps):
        if ts >= probe["duration_sec"]:
            ts = probe["duration_sec"] - 0.5
        frame_p = verification_dir / f"frame_{idx:02d}.jpg"
        cmd = [
            "ffmpeg", "-y",
            "-ss", f"{ts:.2f}",
            "-i", str(video_path),
            "-vframes", "1",
            "-q:v", "2",
            str(frame_p),
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
        with Image.open(frame_p) as f_img:
            # Resize frame for contact sheet (270x480)
            small = f_img.convert("RGB").resize((270, 480), Image.BILINEAR)
            frame_images.append(small)
        frame_p.unlink(missing_ok=True)

    # Grid of 4 columns x 3 rows = 12 frames
    sheet_w = 270 * 4
    sheet_h = 480 * 3
    contact_sheet = Image.new("RGB", (sheet_w, sheet_h), (10, 10, 12))

    for idx, f_im in enumerate(frame_images):
        col = idx % 4
        row = idx // 4
        contact_sheet.paste(f_im, (col * 270, row * 480))

    contact_sheet.save(contact_sheet_path, "JPEG", quality=88)
    assert contact_sheet_path.exists()
    print(f"[+] 12-frame verification contact sheet saved: {contact_sheet_path}")
