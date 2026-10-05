"use client";

import React, { useMemo } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  Node,
  Edge,
  MarkerType,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { PipelineNode, PipelineNodeData } from "./PipelineNode";
import { RunState, StageStatus } from "@/lib/types";

interface PipelineGraphProps {
  runState: RunState;
}

const nodeTypes = {
  pipelineNode: PipelineNode,
};

export function PipelineGraph({ runState }: PipelineGraphProps) {
  const { stages, scenes, currentStage, status, title } = runState;

  // Determine stage status
  const researchStatus: StageStatus = stages.research?.status || "pending";
  const assetStatus: StageStatus = stages.asset?.status || "pending";
  const assemblyStatus: StageStatus = stages.assembly?.status || "pending";
  const isComplete = status === "completed";
  const isFailed = status === "failed";

  // Sub-node statuses for Voice & Visuals based on scene readiness
  const hasVoice = scenes.some((s) => s.audioDurationSec !== undefined);
  const allVoice = scenes.length > 0 && scenes.every((s) => s.audioDurationSec !== undefined);
  const voiceStatus: StageStatus =
    assetStatus === "completed" || allVoice
      ? "completed"
      : assetStatus === "running"
      ? "running"
      : assetStatus === "failed"
      ? "failed"
      : "pending";

  const hasVisuals = scenes.some((s) => s.visualSource !== undefined);
  const allVisuals = scenes.length > 0 && scenes.every((s) => s.visualSource !== undefined);
  const visualsStatus: StageStatus =
    assetStatus === "completed" || allVisuals
      ? "completed"
      : assetStatus === "running"
      ? "running"
      : assetStatus === "failed"
      ? "failed"
      : "pending";

  const outputStatus: StageStatus = isComplete
    ? "completed"
    : isFailed
    ? "failed"
    : assemblyStatus === "running"
    ? "running"
    : "pending";

  const nodes: Node<PipelineNodeData>[] = useMemo(() => {
    return [
      {
        id: "research",
        type: "pipelineNode",
        position: { x: 260, y: 20 },
        data: {
          label: "Research & Script",
          sublabel: "LLM Sequential Gateway",
          type: "research",
          status: researchStatus,
          badge: title ? `"${title.slice(0, 24)}..."` : "Gemini Flash / Pro",
          message:
            researchStatus === "running"
              ? "Drafting pedagogical script & scenes..."
              : researchStatus === "completed"
              ? `${scenes.length || "6"} scenes • 120-140 words verified`
              : "Topic analysis & research",
        },
      },
      {
        id: "voice",
        type: "pipelineNode",
        position: { x: 70, y: 170 },
        data: {
          label: "Voice Narration",
          sublabel: "Edge-TTS + Loudnorm",
          type: "voice",
          status: voiceStatus,
          badge: "Andrew Neural • -16 LUFS",
          message:
            voiceStatus === "running"
              ? "Synthesizing 48kHz audio & word timestamps..."
              : voiceStatus === "completed"
              ? "Full narration mastered at -16 LUFS"
              : "Speech synthesis queue",
        },
      },
      {
        id: "visuals",
        type: "pipelineNode",
        position: { x: 450, y: 170 },
        data: {
          label: "Visual Sourcing",
          sublabel: "Flux Gen / Pexels / Pixabay",
          type: "visuals",
          status: visualsStatus,
          badge: "Smart 9:16 crop • Sobel saliency",
          message:
            visualsStatus === "running"
              ? "Acquiring high-resolution vertical assets..."
              : visualsStatus === "completed"
              ? "Images filtered by perceptual variance & pHash"
              : "Visual assets queue",
        },
      },
      {
        id: "assembly",
        type: "pipelineNode",
        position: { x: 260, y: 320 },
        data: {
          label: "Video Assembly",
          sublabel: "FFmpeg x264 CRF 16 Slow",
          type: "assembly",
          status: assemblyStatus,
          badge: "Float Ken Burns • 60fps Pop Captions",
          message:
            assemblyStatus === "running"
              ? "Compositing motion, vignettes, and karaoke captions..."
              : assemblyStatus === "completed"
              ? "Final 1080x1920 video rendered"
              : "Post-production assembly",
        },
      },
      {
        id: "output",
        type: "pipelineNode",
        position: { x: 260, y: 470 },
        data: {
          label: "Video Delivery",
          sublabel: "HTTP Range 206 Seeking",
          type: "output",
          status: outputStatus,
          badge: isComplete ? `${runState.durationSec?.toFixed(1) || 60}s • 1080x1920` : "Ready for playback",
          message:
            isComplete
              ? "Production video ready for streaming and download."
              : isFailed
              ? "Generation failed. Review error log below."
              : "Waiting for render worker...",
        },
      },
    ];
  }, [
    researchStatus,
    voiceStatus,
    visualsStatus,
    assemblyStatus,
    outputStatus,
    scenes.length,
    title,
    isComplete,
    isFailed,
    runState.durationSec,
  ]);

  const edges: Edge[] = useMemo(() => {
    const getEdgeColor = (sourceStatus: StageStatus, targetStatus: StageStatus) => {
      if (sourceStatus === "completed" && targetStatus === "completed") return "#10B981";
      if (sourceStatus === "completed" || targetStatus === "running") return "#FED766";
      if (sourceStatus === "failed" || targetStatus === "failed") return "#EF4444";
      return "#262B35";
    };

    const c1 = getEdgeColor(researchStatus, voiceStatus);
    const c2 = getEdgeColor(researchStatus, visualsStatus);
    const c3 = getEdgeColor(voiceStatus, assemblyStatus);
    const c4 = getEdgeColor(visualsStatus, assemblyStatus);
    const c5 = getEdgeColor(assemblyStatus, outputStatus);

    return [
      {
        id: "e-research-voice",
        source: "research",
        target: "voice",
        animated: researchStatus === "running" || voiceStatus === "running",
        style: { stroke: c1, strokeWidth: c1 !== "#262B35" ? 2 : 1.5 },
        markerEnd: { type: MarkerType.ArrowClosed, color: c1 },
      },
      {
        id: "e-research-visuals",
        source: "research",
        target: "visuals",
        animated: researchStatus === "running" || visualsStatus === "running",
        style: { stroke: c2, strokeWidth: c2 !== "#262B35" ? 2 : 1.5 },
        markerEnd: { type: MarkerType.ArrowClosed, color: c2 },
      },
      {
        id: "e-voice-assembly",
        source: "voice",
        target: "assembly",
        animated: voiceStatus === "running" || assemblyStatus === "running",
        style: { stroke: c3, strokeWidth: c3 !== "#262B35" ? 2 : 1.5 },
        markerEnd: { type: MarkerType.ArrowClosed, color: c3 },
      },
      {
        id: "e-visuals-assembly",
        source: "visuals",
        target: "assembly",
        animated: visualsStatus === "running" || assemblyStatus === "running",
        style: { stroke: c4, strokeWidth: c4 !== "#262B35" ? 2 : 1.5 },
        markerEnd: { type: MarkerType.ArrowClosed, color: c4 },
      },
      {
        id: "e-assembly-output",
        source: "assembly",
        target: "output",
        animated: assemblyStatus === "running" || (outputStatus === "running" && !isComplete),
        style: { stroke: c5, strokeWidth: c5 !== "#262B35" ? 2 : 1.5 },
        markerEnd: { type: MarkerType.ArrowClosed, color: c5 },
      },
    ];
  }, [researchStatus, voiceStatus, visualsStatus, assemblyStatus, outputStatus, isComplete]);

  return (
    <div className="w-full h-[580px] rounded-2xl glass-panel relative overflow-hidden border border-white/5">
      <div className="absolute top-4 left-4 z-10 flex items-center gap-2 px-3 py-1.5 rounded-lg bg-black/40 border border-white/10 backdrop-blur-md">
        <span
          className={`w-2 h-2 rounded-full ${
            isComplete
              ? "bg-[#10B981] shadow-[0_0_8px_rgba(16,185,129,0.5)]"
              : isFailed
              ? "bg-[#EF4444]"
              : "bg-[#FED766] animate-pulse"
          }`}
        />
        <span className="text-xs font-medium text-white/90">Multi-Agent LangGraph Pipeline</span>
      </div>

      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.15 }}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        zoomOnScroll={false}
        panOnDrag={true}
        className="bg-transparent"
      >
        <Background color="#262B35" gap={20} size={1} />
        <Controls
          showInteractive={false}
          className="!bg-[#141824] !border !border-[#262B35] !rounded-xl !overflow-hidden !shadow-2xl [&>button]:!bg-[#161922] [&>button]:!border-b [&>button]:!border-[#262B35] [&>button]:!fill-[#9CA3AF] hover:[&>button]:!bg-[#222836] hover:[&>button]:!fill-[#FED766] [&>button:last-child]:!border-b-0"
        />
      </ReactFlow>
    </div>
  );
}
