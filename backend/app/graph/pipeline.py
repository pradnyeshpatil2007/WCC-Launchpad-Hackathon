"""LangGraph pipeline orchestrating Research, Asset Acquisition, and Assembly."""

import asyncio
from typing import Any, Callable, Dict, Literal, Optional, TypedDict
from langgraph.graph import END, StateGraph

from app.core.audit_log import finalize_job_log
from app.core.errors import StageError
from app.domain.assets import VisualManifest, VoiceManifest
from app.domain.script import Script
from app.events.bus import EventBus, get_event_bus
from app.events.messages import get_message
from app.graph.assembly import AssemblyAgent
from app.graph.asset import AssetAgent
from app.graph.research import ResearchAgent
from app.jobs.repo import JobRepo


class PipelineState(TypedDict, total=False):
    job_id: str
    prompt: str
    script: Optional[Script]
    voice_manifest: Optional[VoiceManifest]
    visual_manifest: Optional[VisualManifest]
    assembly_result: Optional[Dict[str, Any]]
    tighten_loops: int
    repair_attempts: int
    script_feedback: Optional[str]
    error: Optional[Dict[str, Any]]
    is_cancelled: bool


class AutoShortsPipeline:
    """Multi-agent orchestrator connecting Research, Asset Acquisition, and Assembly."""

    def __init__(self, event_bus: Optional[EventBus] = None, repo: Optional[JobRepo] = None):
        self.event_bus = event_bus or get_event_bus()
        self.repo = repo or JobRepo()
        self.research_agent = ResearchAgent()
        self.asset_agent = AssetAgent()
        self.assembly_agent = AssemblyAgent()
        self.graph = self._build_graph()

    def _build_graph(self):
        builder = StateGraph(PipelineState)

        builder.add_node("research", self._research_node)
        builder.add_node("asset", self._asset_node)
        builder.add_node("assembly", self._assembly_node)
        builder.add_node("failed", self._failed_node)
        builder.add_node("complete", self._complete_node)

        builder.set_entry_point("research")

        builder.add_conditional_edges(
            "research",
            self._route_after_research,
            {
                "research": "research",
                "asset": "asset",
                "failed": "failed",
            },
        )

        builder.add_conditional_edges(
            "asset",
            self._route_after_asset,
            {
                "research": "research",
                "assembly": "assembly",
                "failed": "failed",
            },
        )

        builder.add_conditional_edges(
            "assembly",
            self._route_after_assembly,
            {
                "complete": "complete",
                "failed": "failed",
            },
        )

        builder.add_edge("complete", END)
        builder.add_edge("failed", END)

        return builder.compile()

    # --- NODE IMPLEMENTATIONS ---

    async def _research_node(self, state: PipelineState) -> Dict[str, Any]:
        job_id = state["job_id"]
        prompt = state["prompt"]
        tighten = state.get("tighten_loops", 0)
        feedback = state.get("script_feedback")

        await self.repo.update_job_status(job_id, status="running", current_stage="research", progress=0.10)
        await self.event_bus.publish(
            job_id,
            "stage.started",
            {"stage": "research", "message": get_message("research.started")},
        )

        def event_cb(ev_type: str, payload: Dict[str, Any]):
            asyncio.create_task(self.event_bus.publish(job_id, ev_type, payload))

        try:
            script = await self.research_agent.execute(
                prompt=prompt,
                job_id=job_id,
                tighten_feedback=feedback,
                event_cb=event_cb,
            )

            await self.event_bus.publish(
                job_id,
                "script.ready",
                {
                    "title": script.title,
                    "sceneCount": len(script.scenes),
                    "wordCount": script.total_words,
                },
            )

            await self.event_bus.publish(
                job_id,
                "stage.completed",
                {
                    "stage": "research",
                    "durationMs": 1000,
                    "message": get_message("research.completed", word_count=script.total_words, scene_count=len(script.scenes)),
                },
            )

            return {
                "script": script,
                "script_feedback": None,
                "error": None,
            }

        except Exception as e:
            import traceback
            traceback.print_exc()
            attempts = state.get("repair_attempts", 0) + 1
            code = getattr(e, "code", "RESEARCH_FAILED")
            msg = str(e) or repr(e) or "Research stage failed"
            return {
                "repair_attempts": attempts,
                "error": {"stage": "research", "code": code, "message": msg, "retryable": attempts < 3},
            }

    async def _asset_node(self, state: PipelineState) -> Dict[str, Any]:
        job_id = state["job_id"]
        script = state["script"]
        if not script:
            return {"error": {"stage": "asset", "code": "MISSING_SCRIPT", "message": "Script not available", "retryable": False}}

        await self.repo.update_job_status(job_id, status="running", current_stage="asset", progress=0.35)
        await self.event_bus.publish(
            job_id,
            "stage.started",
            {"stage": "asset", "message": get_message("asset.started")},
        )

        def event_cb(ev_type: str, payload: Dict[str, Any]):
            asyncio.create_task(self.event_bus.publish(job_id, ev_type, payload))

        try:
            voice_manifest, visual_manifest = await self.asset_agent.execute(
                script=script,
                job_id=job_id,
                event_cb=event_cb,
            )

            await self.event_bus.publish(
                job_id,
                "stage.completed",
                {"stage": "asset", "durationMs": 2000, "message": get_message("asset.completed")},
            )

            return {
                "voice_manifest": voice_manifest,
                "visual_manifest": visual_manifest,
                "error": None,
            }

        except StageError as e:
            if e.code == "AUDIO_OVER_BUDGET" and state.get("tighten_loops", 0) < 2:
                tighten_count = state.get("tighten_loops", 0) + 1
                return {
                    "tighten_loops": tighten_count,
                    "script_feedback": "Audio duration was slightly over 60s. Please tighten script by 5-8 words.",
                    "error": {"stage": "asset", "code": e.code, "message": e.message, "retryable": True},
                }
            return {"error": {"stage": "asset", "code": e.code, "message": e.message, "retryable": e.retryable}}

        except Exception as e:
            import traceback
            traceback.print_exc()
            msg = str(e) or repr(e) or "Asset stage failed"
            return {"error": {"stage": "asset", "code": "ASSET_FAILED", "message": msg, "retryable": False}}

    async def _assembly_node(self, state: PipelineState) -> Dict[str, Any]:
        job_id = state["job_id"]
        script = state["script"]
        voice = state["voice_manifest"]
        visuals = state["visual_manifest"]

        await self.repo.update_job_status(job_id, status="running", current_stage="assembly", progress=0.70)
        await self.event_bus.publish(
            job_id,
            "stage.started",
            {"stage": "assembly", "message": get_message("assembly.started")},
        )

        def event_cb(ev_type: str, payload: Dict[str, Any]):
            asyncio.create_task(self.event_bus.publish(job_id, ev_type, payload))

        try:
            assembly_result = await self.assembly_agent.execute(
                script=script,
                voice=voice,
                visuals=visuals,
                job_id=job_id,
                event_cb=event_cb,
            )

            await self.event_bus.publish(
                job_id,
                "stage.completed",
                {"stage": "assembly", "durationMs": 3000, "message": get_message("assembly.completed")},
            )

            return {
                "assembly_result": assembly_result,
                "error": None,
            }

        except StageError as e:
            return {"error": {"stage": "assembly", "code": e.code, "message": e.message, "retryable": e.retryable}}
        except Exception as e:
            import traceback
            traceback.print_exc()
            msg = str(e) or repr(e) or "Assembly stage failed"
            return {"error": {"stage": "assembly", "code": "ASSEMBLY_FAILED", "message": msg, "retryable": False}}

    async def _complete_node(self, state: PipelineState) -> Dict[str, Any]:
        job_id = state["job_id"]
        res = state.get("assembly_result", {})
        vid_url = f"/api/media/{job_id}/video.mp4"
        thumb_url = f"/api/media/{job_id}/thumbnail.jpg"
        dur_sec = res.get("duration_sec", 60.0)

        # Calculate scene start times
        voice = state.get("voice_manifest")
        starts = [0.4]
        if voice:
            cur = 0.4
            for s in voice.scenes[:-1]:
                cur += s.duration_sec + 0.12
                starts.append(round(cur, 2))

        await self.repo.update_job_status(
            job_id,
            status="completed",
            current_stage="complete",
            progress=1.0,
            video_url=vid_url,
            thumbnail_url=thumb_url,
            duration_sec=dur_sec,
        )

        await self.event_bus.publish(
            job_id,
            "job.completed",
            {
                "videoUrl": vid_url,
                "thumbnailUrl": thumb_url,
                "durationSec": dur_sec,
                "sceneStartTimes": starts,
            },
        )

        script = state.get("script")
        title = script.title if script else None
        prompt = state.get("prompt", "")
        finalize_job_log(
            job_id=job_id,
            prompt=prompt,
            status="completed",
            title=title,
            duration_sec=dur_sec,
        )

        return {}

    async def _failed_node(self, state: PipelineState) -> Dict[str, Any]:
        job_id = state["job_id"]
        err = state.get("error", {"stage": "unknown", "code": "INTERNAL_ERROR", "message": "Job failed", "retryable": False})

        await self.repo.update_job_status(
            job_id,
            status="failed",
            error_code=err.get("code"),
            error_message=err.get("message"),
        )

        await self.event_bus.publish(
            job_id,
            "job.failed",
            {
                "stage": err.get("stage", "unknown"),
                "code": err.get("code", "INTERNAL_ERROR"),
                "message": err.get("message", "Job failed"),
                "retryable": err.get("retryable", False),
            },
        )

        script = state.get("script")
        title = script.title if script else None
        prompt = state.get("prompt", "")
        finalize_job_log(
            job_id=job_id,
            prompt=prompt,
            status="failed",
            title=title,
            error=err,
        )

        return {}

    # --- ROUTING RULES ---

    def _route_after_research(self, state: PipelineState) -> Literal["research", "asset", "failed"]:
        if state.get("error"):
            if state.get("repair_attempts", 0) < 3:
                return "research"
            return "failed"
        return "asset"

    def _route_after_asset(self, state: PipelineState) -> Literal["research", "assembly", "failed"]:
        err = state.get("error")
        if err:
            if err.get("code") == "AUDIO_OVER_BUDGET" and state.get("tighten_loops", 0) < 2:
                return "research"
            return "failed"
        return "assembly"

    def _route_after_assembly(self, state: PipelineState) -> Literal["complete", "failed"]:
        if state.get("error"):
            return "failed"
        return "complete"

    async def run(self, job_id: str, prompt: str) -> Dict[str, Any]:
        """Execute full pipeline from prompt to finished video."""
        initial_state: PipelineState = {
            "job_id": job_id,
            "prompt": prompt,
            "tighten_loops": 0,
            "repair_attempts": 0,
        }
        return await self.graph.ainvoke(initial_state)
