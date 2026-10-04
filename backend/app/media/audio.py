"""Audio processing: silence trimming, alignment, gap concatenation, and loudness normalization."""

import asyncio
import json
from pathlib import Path
import subprocess
from typing import Any, Dict, List, Tuple

from app.config import get_settings
from app.domain.assets import WordTiming


def get_media_duration(file_path: Path) -> float:
    """Use ffprobe to accurately read media duration in seconds."""
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(file_path),
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
    return float(res.stdout.strip())


async def convert_and_trim_audio(
    input_mp3_path: Path,
    output_wav_path: Path,
    raw_word_timings: List[Dict[str, Any]],
) -> Tuple[float, List[WordTiming]]:
    """Convert MP3 to 48kHz mono WAV, trim silence, probe duration, and adjust timings."""
    output_wav_path.parent.mkdir(parents=True, exist_ok=True)

    # Use ffmpeg silenceremove filter to trim leading silence (>0.05s below -45dB)
    cmd = [
        "ffmpeg",
        "-y",
        "-i", str(input_mp3_path),
        "-af", "silenceremove=start_periods=1:start_duration=0.05:start_threshold=-45dB",
        "-ar", "48000",
        "-ac", "1",
        str(output_wav_path),
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        # Fallback without silenceremove if filter fails
        fallback_cmd = [
            "ffmpeg", "-y", "-i", str(input_mp3_path),
            "-ar", "48000", "-ac", "1", str(output_wav_path),
        ]
        p2 = await asyncio.create_subprocess_exec(*fallback_cmd)
        await p2.communicate()

    duration = get_media_duration(output_wav_path)

    # Adjust word timings
    adjusted_timings: List[WordTiming] = []
    if raw_word_timings:
        first_start = raw_word_timings[0].get("offset_sec", 0.0)
        last_end = raw_word_timings[-1].get("offset_sec", 0.0) + raw_word_timings[-1].get("duration_sec", 0.0)
        scale = (duration / last_end) if last_end > 0 else 1.0

        for item in raw_word_timings:
            start_s = max(0.0, (item.get("offset_sec", 0.0) - first_start * 0.5) * scale)
            end_s = min(duration, start_s + item.get("duration_sec", 0.2) * scale)
            adjusted_timings.append(
                WordTiming(
                    text=item.get("text", "").strip(),
                    start=round(start_s, 3),
                    end=round(end_s, 3),
                )
            )

    return duration, adjusted_timings


async def assemble_narration_audio(
    scene_wav_paths: List[Path],
    output_narration_path: Path,
    lead_in: float = 0.4,
    gap_duration: float = 0.12,
    tail: float = 0.6,
    target_lufs: float = -16.0,
) -> float:
    """Concatenate scenes with lead-in, inter-scene gaps, tail, and apply loudnorm."""
    settings = get_settings()
    output_narration_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_concat = output_narration_path.with_suffix(".unnorm.wav")

    # Generate silence files for gaps
    storage_tmp = output_narration_path.parent / "tmp"
    storage_tmp.mkdir(parents=True, exist_ok=True)
    gap_wav = storage_tmp / "gap_120ms.wav"
    lead_wav = storage_tmp / "lead_in.wav"
    tail_wav = storage_tmp / "tail.wav"

    for path, dur in [(gap_wav, gap_duration), (lead_wav, lead_in), (tail_wav, tail)]:
        if not path.exists():
            subprocess.run(
                ["ffmpeg", "-y", "-f", "lavfi", "-i", f"anullsrc=r=48000:cl=mono:d={dur}", str(path)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

    # Build concat file list
    concat_list = storage_tmp / "concat_list.txt"
    with concat_list.open("w", encoding="utf-8") as f:
        f.write(f"file '{lead_wav.as_posix()}'\n")
        for i, s_wav in enumerate(scene_wav_paths):
            f.write(f"file '{s_wav.as_posix()}'\n")
            if i < len(scene_wav_paths) - 1:
                f.write(f"file '{gap_wav.as_posix()}'\n")
        f.write(f"file '{tail_wav.as_posix()}'\n")

    # Concatenate
    cmd_concat = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
        "-c", "pcm_s16le", str(tmp_concat),
    ]
    proc_concat = await asyncio.create_subprocess_exec(*cmd_concat, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    await proc_concat.communicate()

    # Apply 2-pass EBU R128 loudnorm
    cmd_loudnorm = [
        "ffmpeg", "-y", "-i", str(tmp_concat),
        "-af", f"loudnorm=I={target_lufs}:TP=-1.0:LRA=11",
        "-ar", "48000", "-ac", "2",
        str(output_narration_path),
    ]
    proc_norm = await asyncio.create_subprocess_exec(*cmd_loudnorm, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    await proc_norm.communicate()

    if tmp_concat.exists():
        tmp_concat.unlink()

    return get_media_duration(output_narration_path)
