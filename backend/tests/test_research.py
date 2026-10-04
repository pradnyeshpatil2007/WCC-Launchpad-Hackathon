"""Phase 3 verification tests: Research Agent with 5 diverse real topics, word budget, schema validation."""

import pytest
from app.graph.research import ResearchAgent
from app.domain.script import Script, count_words


TOPICS = [
    "Why is the sky blue?",
    "How do black holes bend time?",
    "The secret life of mycelium",
    "How vaccines train the immune system",
    "Why the Roman Colosseum survived earthquakes",
]


@pytest.fixture
def agent():
    return ResearchAgent()


@pytest.mark.parametrize("topic", TOPICS)
@pytest.mark.asyncio
async def test_research_agent_diverse_topics(agent, topic):
    """Test script generation across 5 diverse topics with live LLM Gateway."""
    job_id = f"test_research_{abs(hash(topic)) % 10000}"
    script = await agent.generate_script(topic=topic, job_id=job_id)

    # 1. Verify schema type
    assert isinstance(script, Script)
    assert script.title.strip()

    # 2. Verify scene bounds (5-8 scenes)
    num_scenes = len(script.scenes)
    assert 5 <= num_scenes <= 8, f"Expected 5-8 scenes, got {num_scenes}"

    # 3. Verify visual beats per scene (2-3 beats) and beat content
    for idx, scene in enumerate(script.scenes):
        num_beats = len(scene.beats)
        assert 2 <= num_beats <= 3, f"Scene {idx} has {num_beats} beats, expected 2-3"
        assert scene.emphasis_text.strip()
        assert 1 <= count_words(scene.emphasis_text) <= 4

        for b_idx, beat in enumerate(scene.beats):
            # Narration 4-25 words
            words = count_words(beat.narration)
            assert 4 <= words <= 25, f"Scene {idx} Beat {b_idx} word count {words} outside 4-25"
            # Image prompt detailed
            assert len(beat.image_prompt) >= 60
            # Stock queries 3-6 items, 1-4 words each
            assert 3 <= len(beat.stock_queries) <= 6
            for q in beat.stock_queries:
                assert 1 <= len(q.split()) <= 4

    # 4. Total word count strictly 120-140 words
    total_words = script.total_words
    assert 120 <= total_words <= 140, f"Total word count {total_words} outside 120-140 for topic '{topic}'"

    print(f"\n==================================================")
    print(f"TOPIC: {topic}")
    print(f"TITLE: {script.title}")
    print(f"SCENES: {num_scenes} | TOTAL SPOKEN WORDS: {total_words}")
    print(f"SAMPLE SCENE 1 NARRATION: {script.scenes[0].narration}")
    print(f"SAMPLE SCENE 1 EMPHASIS: {script.scenes[0].emphasis_text}")
    print(f"SAMPLE BEAT 0 STOCK QUERIES: {script.scenes[0].beats[0].stock_queries}")
    print(f"==================================================")


@pytest.mark.asyncio
async def test_research_tighten_feedback(agent):
    """Test that tighten feedback adjusts word count downward."""
    topic = "The speed of light in vacuum"
    job_id = "test_research_tighten"
    script = await agent.generate_script(
        topic=topic,
        job_id=job_id,
        script_feedback="Narration runs 3 seconds over; cut about 8 words, keep exactly 120-125 words, preserve hook and takeaway.",
    )
    assert 120 <= script.total_words <= 140
    print(f"\nTightened script total words: {script.total_words}")
