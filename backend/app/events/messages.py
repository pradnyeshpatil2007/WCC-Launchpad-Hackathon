"""Canonical messages catalog for sanitized, friendly UI copy."""

MESSAGES = {
    # Research / Script
    "research.started": "Researching topic and drafting educational script",
    "research.repair": "Refining script to meet formatting constraints (attempt {attempt}/{max_attempts})",
    "research.tighten": "Tightening script pacing and spoken word budget",
    "research.completed": "Script drafted ({word_count} words across {scene_count} scenes)",

    # Asset Stage
    "asset.started": "Acquiring media assets: voiceover and visuals in parallel",
    "asset.voice.started": "Synthesizing narration with Edge-TTS voice engine",
    "asset.voice.bump": "Pacing audio within duration budget (+{rate_bump}% rate)",
    "asset.voice.completed": "Voiceover audio mastered (-16 LUFS EBU R128)",
    "asset.visuals.started": "Acquiring vertical 9:16 portrait visual imagery",
    "asset.visuals.generated": "Synthesized scene {scene_num} key visual via Flux",
    "asset.visuals.stock": "Curated photographic stock asset for scene {scene_num}",
    "asset.fallback.model": "Switched to backup model sequence",
    "asset.fallback.stock": "Using curated photographic stock imagery for scene {scene_num}",
    "asset.completed": "All visual and audio assets acquired and validated",

    # Assembly Stage
    "assembly.started": "Calculating Ken Burns motion curves and caption timings",
    "assembly.render": "Rendering master video (1080x1920 30fps x264 CRF 16)",
    "assembly.completed": "Master video rendered and verified via ffprobe",

    # Pipeline Level
    "pipeline.completed": "Video generation finished successfully",
    "pipeline.cancelled": "Job was cancelled by user",
    "pipeline.failed": "Pipeline halted due to error in stage '{stage}'",
}


def get_message(key: str, **kwargs) -> str:
    """Retrieve message from catalogue and interpolate parameters safely."""
    tmpl = MESSAGES.get(key, key)
    try:
        return tmpl.format(**kwargs)
    except Exception:
        return tmpl
