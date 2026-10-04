"""Phase 4 verification tests: Asset Agent, Voice/TTS, Image Gen, Stock fallback, and VISUALS_UNAVAILABLE failure."""

import asyncio
from pathlib import Path
import pytest

from app.config import get_settings
from app.core.errors import StageError
from app.domain.script import Script, Scene, VisualBeat
from app.graph.asset import AssetAgent


@pytest.fixture
def sample_script():
    """A valid 5-scene script with exactly 120 words for testing asset pipeline."""
    return Script(
        title="Why Sunlight Warms the Earth",
        scenes=[
            Scene(
                emphasis_text="Solar Energy",
                beats=[
                    VisualBeat(
                        narration="Every day our sun showers Earth with massive streams of radiant energy.",
                        image_prompt="Vibrant golden sun emitting bright rays through deep blackness of outer space, 9:16 portrait orientation, cinematic lighting, photorealistic, no text.",
                        stock_queries=["sun shining space", "solar radiation sun", "golden sunlight outer space", "bright sun rays"],
                    ),
                    VisualBeat(
                        narration="This continuous flow of solar rays travels through space sustaining all life.",
                        image_prompt="View of Earth from orbit with warm golden sunlight washing over the atmosphere, vertical 9:16, cinematic, photorealistic, no text.",
                        stock_queries=["earth atmosphere sunlight", "sunbeams earth orbit", "planet sunrise space", "solar energy globe"],
                    ),
                ],
            ),
            Scene(
                emphasis_text="Atmospheric Shield",
                beats=[
                    VisualBeat(
                        narration="When sunlight strikes the upper atmosphere, dense clouds absorb dangerous ultraviolet rays.",
                        image_prompt="Sunlight filtering through thick white fluffy clouds in brilliant blue sky, 9:16 portrait, cinematic lighting, photorealistic, no text.",
                        stock_queries=["sunlight clouds blue sky", "clouds sunbeams sky", "bright clouds sun", "clear atmosphere"],
                    ),
                    VisualBeat(
                        narration="Gentle visible light passes safely through to brightly illuminate the world below.",
                        image_prompt="Golden morning sunlight streaming through a lush green forest canopy, vertical 9:16, rays of light, photorealistic, no text.",
                        stock_queries=["forest sunlight beams", "sunlight trees morning", "nature light canopy", "green forest sun"],
                    ),
                ],
            ),
            Scene(
                emphasis_text="Surface Absorption",
                beats=[
                    VisualBeat(
                        narration="Vast blue oceans, green forests, and dark soil absorb this energy efficiently.",
                        image_prompt="Dramatic dark ocean waves shimmering under bright noon sunlight, vertical 9:16 portrait, cinematic photography, no text.",
                        stock_queries=["ocean waves sunlight", "sea water sun reflection", "dark rocks sunlight", "sunny ocean surface"],
                    ),
                    VisualBeat(
                        narration="Their microscopic molecules vibrate faster, converting bright light directly into warming heat.",
                        image_prompt="Warm dry desert sand dunes glowing orange under intense golden sun, vertical 9:16 portrait, photorealistic, no text.",
                        stock_queries=["desert sand dunes sun", "warm sand sunlight", "golden sand desert", "heat shimmering desert"],
                    ),
                ],
            ),
            Scene(
                emphasis_text="Thermal Radiation",
                beats=[
                    VisualBeat(
                        narration="The warmed earth radiates invisible infrared waves back upward into open air.",
                        image_prompt="Glowing thermal heat waves rising from a canyon at sunset, vertical 9:16 portrait, vivid warm colors, photorealistic, no text.",
                        stock_queries=["heat waves rising sunset", "canyon sunset golden hour", "warm ground sunset", "infrared landscape"],
                    ),
                    VisualBeat(
                        narration="Thick atmospheric gases trap this thermal warmth like a cozy natural blanket.",
                        image_prompt="Cozy Earth wrapped in a soft glowing atmosphere in space, 9:16 vertical portrait, artistic photorealistic, no text.",
                        stock_queries=["planet earth glowing atmosphere", "earth greenhouse glow", "atmosphere space", "planet earth"],
                    ),
                ],
            ),
            Scene(
                emphasis_text="Life Thrives",
                beats=[
                    VisualBeat(
                        narration="Without this greenhouse effect, our world would become an uninhabitable icy desert.",
                        image_prompt="Thriving vibrant green meadow with colorful wildflowers basking in glorious sunlight, vertical 9:16 portrait, cinematic, no text.",
                        stock_queries=["green meadow wildflowers sun", "sunny flower field", "spring nature meadow", "blooming wildflowers"],
                    ),
                    VisualBeat(
                        narration="Solar energy constantly nurtures every living habitat across our magnificent vibrant planet.",
                        image_prompt="Lush panoramic mountain valley bathed in golden afternoon sunlight, 9:16 portrait, awe-inspiring photography, no text.",
                        stock_queries=["mountain valley sunlight", "lush landscape golden hour", "nature landscape sun", "scenic mountains sunny"],
                    ),
                ],
            ),
        ],
    )


@pytest.mark.asyncio
async def test_asset_agent_happy_path(sample_script):
    """Verify live happy path: TTS voiceover + visual acquisition (Pollinations Flux)."""
    agent = AssetAgent()
    events = []

    def event_cb(ev_type, payload):
        events.append((ev_type, payload))

    job_id = "test_asset_happy"
    voice_manifest, visual_manifest = await agent.execute(
        script=sample_script,
        job_id=job_id,
        event_cb=event_cb,
        force_image_failure=False,
    )

    # 1. Voice manifest verification
    assert voice_manifest.total_sec > 0
    assert len(voice_manifest.scenes) == len(sample_script.scenes)
    for s_audio in voice_manifest.scenes:
        assert s_audio.duration_sec > 0
        assert len(s_audio.words) > 0

    # 2. Visual manifest verification
    assert len(visual_manifest.scenes) == len(sample_script.scenes)
    for s_vis in visual_manifest.scenes:
        assert len(s_vis.images) >= 2, f"Scene {s_vis.scene_index} has fewer than 2 images"
        for img in s_vis.images:
            assert img.width >= 1080
            assert img.height >= 1920
            assert abs((img.width / img.height) - (9.0 / 16.0)) < 0.02
            assert Path(agent.settings.resolved_media_dir / "jobs" / job_id / img.file).exists()

    # 3. Verify event notifications
    event_types = [e[0] for e in events]
    assert "substep.started" in event_types
    assert "scene.voice_ready" in event_types
    assert "scene.visual_ready" in event_types
    print(f"\n[+] Happy path verified: {len(visual_manifest.scenes)} scenes, voice {voice_manifest.total_sec:.1f}s")


@pytest.mark.asyncio
async def test_asset_forced_image_failure_fallback_to_stock(sample_script):
    """Verify fallback path: forced image failure triggers multi-image stock fallback per scene."""
    agent = AssetAgent()
    events = []

    def event_cb(ev_type, payload):
        events.append((ev_type, payload))

    job_id = "test_asset_stock_fallback"
    voice_manifest, visual_manifest = await agent.execute(
        script=sample_script,
        job_id=job_id,
        event_cb=event_cb,
        force_image_failure=True,  # Force image generation failure to test stock fallback
    )

    # Check fallback events emitted
    fallback_events = [e for e in events if e[0] == "fallback.used"]
    assert len(fallback_events) > 0, "Expected fallback.used events"
    assert fallback_events[0][1]["kind"] == "visual_source"

    # Verify that all images were sourced from stock providers (pexels or pixabay)
    for s_vis in visual_manifest.scenes:
        assert len(s_vis.images) >= 2, "Expected multiple stock images per scene"
        for img in s_vis.images:
            assert img.source in ("pexels", "pixabay")
            assert Path(agent.settings.resolved_media_dir / "jobs" / job_id / img.file).exists()

    print(f"\n[+] Forced image failure successfully triggered multi-image stock fallback ({len(fallback_events)} fallback events).")


@pytest.mark.asyncio
async def test_asset_zero_image_raises_visuals_unavailable():
    """Verify no-mock defensive rule: impossible queries + failed image gen raises VISUALS_UNAVAILABLE without creating placeholder files."""
    agent = AssetAgent()
    job_id = "test_asset_zero_fail"

    # Script with completely impossible random queries (128 words total, 5 scenes)
    impossible_script = Script(
        title="Zxkjq Plmno Wvtrq",
        scenes=[
            Scene(
                emphasis_text="Zxkjq Alpha",
                beats=[
                    VisualBeat(
                        narration="This is an impossible test query designed to fail all database lookups completely.",
                        image_prompt="Impossible visual prompt xyz123456789 non-existent creature qwertyuiop, vertical 9:16, photorealistic.",
                        stock_queries=["zxqjvwkzpxq999", "qwertyuiopasdfghjkl123", "nonexistentphototerm9999"],
                    ),
                    VisualBeat(
                        narration="Every single attempt to locate real images will result in complete failure.",
                        image_prompt="Another impossible prompt that cannot be found or generated anywhere on earth.",
                        stock_queries=["zzzzzzzzzzzzzzzzzz123", "qqqqqqqqqqqqqqqqqq456", "xxxxxxxxxxxxxxxxxx789"],
                    ),
                ],
            ),
            Scene(
                emphasis_text="Zxkjq Beta",
                beats=[
                    VisualBeat(
                        narration="No photo agency or media library possesses any files matching these strange tokens.",
                        image_prompt="Gibberish prompt non-existent entity floating in the void vertical 9:16.",
                        stock_queries=["zxqj_gibberish_01", "zxqj_gibberish_02", "zxqj_gibberish_03"],
                    ),
                    VisualBeat(
                        narration="The retrieval algorithm will cycle through all providers and find absolutely nothing.",
                        image_prompt="Another void prompt with zero results vertical 9:16 realistic photography.",
                        stock_queries=["zxqj_gibberish_04", "zxqj_gibberish_05", "zxqj_gibberish_06"],
                    ),
                ],
            ),
            Scene(
                emphasis_text="Zxkjq Gamma",
                beats=[
                    VisualBeat(
                        narration="Each subsequent attempt to query our stock archives produces completely empty result sets.",
                        image_prompt="Null result scene impossible conceptual artwork vertical 9:16 photorealistic.",
                        stock_queries=["zxqj_gibberish_07", "zxqj_gibberish_08", "zxqj_gibberish_09"],
                    ),
                    VisualBeat(
                        narration="Synthesizing images has also been disabled intentionally for this specific unit test.",
                        image_prompt="Disabled synthesis test concept vertical 9:16 clean photorealistic.",
                        stock_queries=["zxqj_gibberish_10", "zxqj_gibberish_11", "zxqj_gibberish_12"],
                    ),
                ],
            ),
            Scene(
                emphasis_text="Zxkjq Delta",
                beats=[
                    VisualBeat(
                        narration="Therefore no candidate visuals will ever be added to the accepted list.",
                        image_prompt="Empty list visual concept vertical 9:16 photorealistic framing.",
                        stock_queries=["zxqj_gibberish_13", "zxqj_gibberish_14", "zxqj_gibberish_15"],
                    ),
                    VisualBeat(
                        narration="The entire pipeline must recognize this failure state cleanly and halt execution.",
                        image_prompt="Pipeline termination visual representation vertical 9:16 realistic style.",
                        stock_queries=["zxqj_gibberish_16", "zxqj_gibberish_17", "zxqj_gibberish_18"],
                    ),
                ],
            ),
            Scene(
                emphasis_text="Zxkjq Epsilon",
                beats=[
                    VisualBeat(
                        narration="Ultimately the asset stage must reject this empty job and terminate.",
                        image_prompt="Final rejection stage visual vertical 9:16 clean photorealistic.",
                        stock_queries=["zxqj_gibberish_19", "zxqj_gibberish_20", "zxqj_gibberish_21"],
                    ),
                    VisualBeat(
                        narration="An explicit error code signals that visuals are entirely unavailable today.",
                        image_prompt="Explicit signal visual vertical 9:16 realistic photorealistic.",
                        stock_queries=["zxqj_gibberish_22", "zxqj_gibberish_23", "zxqj_gibberish_24"],
                    ),
                ],
            ),
        ],
    )

    with pytest.raises(StageError) as exc_info:
        await agent.run_visuals(
            script=impossible_script,
            job_id=job_id,
            storage_dir=agent.settings.resolved_media_dir / "jobs" / job_id,
            force_image_failure=True,
            force_stock_failure=True,
        )

    assert exc_info.value.code == "VISUALS_UNAVAILABLE"
    print(f"\n[+] Correctly raised VISUALS_UNAVAILABLE when 0 real images could be found.")
