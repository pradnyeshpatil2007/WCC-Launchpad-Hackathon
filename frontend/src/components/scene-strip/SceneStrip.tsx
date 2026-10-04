"use client";

import React from "react";
import { SceneData } from "@/lib/types";
import { Mic, Image as ImageIcon, Sparkles, CheckCircle2 } from "lucide-react";

interface SceneStripProps {
  scenes: SceneData[];
  selectedSceneIndex: number | null;
  onSelectScene: (index: number) => void;
  sceneStartTimes?: number[] | null;
}

export function SceneStrip({
  scenes,
  selectedSceneIndex,
  onSelectScene,
  sceneStartTimes,
}: SceneStripProps) {
  if (!scenes || scenes.length === 0) {
    return (
      <div className="w-full rounded-2xl glass-panel p-6 text-center text-[#6B7280] text-xs">
        Scenes will populate automatically once script research is finalized...
      </div>
    );
  }

  return (
    <div className="w-full rounded-2xl glass-panel p-4 border border-white/5">
      <div className="flex items-center justify-between mb-3 px-1">
        <h3 className="text-xs font-semibold text-white tracking-wide uppercase flex items-center gap-2">
          <span>Scene Storyboard</span>
          <span className="text-[10px] text-[#9CA3AF] bg-[#222836] px-2 py-0.5 rounded-full font-mono">
            {scenes.length} beats
          </span>
        </h3>
        <span className="text-[11px] text-[#9CA3AF]">
          Click scene to jump timeline
        </span>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
        {scenes.map((scene, idx) => {
          const isSelected = selectedSceneIndex === idx;
          const hasVoice = scene.audioDurationSec !== undefined;
          const hasVisuals = scene.visualSource !== undefined;
          const startTime = sceneStartTimes && sceneStartTimes[idx] !== undefined
            ? sceneStartTimes[idx]
            : null;

          return (
            <button
              key={idx}
              onClick={() => onSelectScene(idx)}
              className={`flex flex-col text-left rounded-xl p-2.5 transition-all duration-200 border ${
                isSelected
                  ? "border-[#FED766] bg-[#FED766]/10 shadow-[0_0_15px_rgba(254,215,102,0.15)]"
                  : "border-white/5 bg-[#161922]/70 hover:border-white/20 hover:bg-[#1A1F2B]"
              }`}
            >
              {/* Thumbnail Container */}
              <div className="w-full aspect-[9/16] rounded-lg bg-[#0E1015] border border-white/5 relative overflow-hidden mb-2 flex items-center justify-center">
                {scene.previewUrl ? (
                  <img
                    src={scene.previewUrl}
                    alt={`Scene ${idx + 1}`}
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <div className="flex flex-col items-center gap-1.5 text-[#4B5563]">
                    <ImageIcon className="w-5 h-5 animate-pulse" />
                    <span className="text-[10px]">Sourcing...</span>
                  </div>
                )}

                {/* Source Badge */}
                {scene.visualSource && (
                  <span className="absolute top-1.5 right-1.5 px-1.5 py-0.5 rounded text-[9px] font-medium bg-black/70 backdrop-blur-sm text-white border border-white/10 flex items-center gap-1">
                    {scene.visualSource === "generated" ? (
                      <>
                        <Sparkles className="w-2.5 h-2.5 text-[#FED766]" />
                        <span>Flux</span>
                      </>
                    ) : (
                      <>
                        <ImageIcon className="w-2.5 h-2.5 text-[#60A5FA]" />
                        <span>Stock</span>
                      </>
                    )}
                  </span>
                )}

                {/* Start Time Badge */}
                {startTime !== null && (
                  <span className="absolute bottom-1.5 left-1.5 px-1.5 py-0.5 rounded text-[9px] font-mono bg-black/70 backdrop-blur-sm text-[#D1D5DB]">
                    {startTime.toFixed(1)}s
                  </span>
                )}
              </div>

              {/* Scene Info */}
              <div className="flex items-center justify-between w-full">
                <span className="text-xs font-semibold text-white">
                  Scene {idx + 1}
                </span>

                <div className="flex items-center gap-1.5">
                  {/* Voice badge */}
                  <span
                    className={`flex items-center gap-0.5 text-[10px] ${
                      hasVoice ? "text-[#10B981]" : "text-[#4B5563]"
                    }`}
                    title={hasVoice ? `${scene.audioDurationSec?.toFixed(1)}s audio` : "Pending audio"}
                  >
                    <Mic className="w-3 h-3" />
                    {hasVoice && <span>{scene.audioDurationSec?.toFixed(0)}s</span>}
                  </span>
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
