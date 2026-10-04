"use client";

import React from "react";
import { Handle, Position } from "@xyflow/react";
import { CheckCircle2, AlertCircle, Loader2, Clock, Sparkles, Mic, Image as ImageIcon, Film, Terminal } from "lucide-react";
import { StageStatus } from "@/lib/types";

export interface PipelineNodeData extends Record<string, unknown> {
  label: string;
  sublabel?: string;
  type: "research" | "voice" | "visuals" | "assembly" | "output";
  status: StageStatus;
  progress?: number;
  message?: string;
  badge?: string;
  durationMs?: number;
}

const nodeIcons = {
  research: Sparkles,
  voice: Mic,
  visuals: ImageIcon,
  assembly: Film,
  output: Terminal,
};

export function PipelineNode({ data }: { data: PipelineNodeData }) {
  const Icon = nodeIcons[data.type] || Sparkles;

  const isRunning = data.status === "running";
  const isCompleted = data.status === "completed";
  const isFailed = data.status === "failed";
  const isPending = data.status === "pending";

  let borderClass = "border-[#262B35]";
  let bgClass = "bg-[#161922]/90";
  let statusBadge = null;

  if (isRunning) {
    borderClass = "border-[#FED766] shadow-[0_0_20px_rgba(254,215,102,0.3)] animate-glow";
    bgClass = "bg-[#1C202C]";
    statusBadge = (
      <span className="flex items-center gap-1 text-[11px] font-medium text-[#FED766] bg-[#FED766]/10 px-2 py-0.5 rounded-full border border-[#FED766]/20">
        <Loader2 className="w-3 h-3 animate-spin" />
        {data.progress ? `${Math.round(data.progress * 100)}%` : "Running"}
      </span>
    );
  } else if (isCompleted) {
    borderClass = "border-[#10B981]/50 shadow-[0_0_15px_rgba(16,185,129,0.15)]";
    bgClass = "bg-[#14231E]/80";
    statusBadge = (
      <span className="flex items-center gap-1 text-[11px] font-medium text-[#10B981] bg-[#10B981]/10 px-2 py-0.5 rounded-full border border-[#10B981]/20">
        <CheckCircle2 className="w-3 h-3" />
        Done
      </span>
    );
  } else if (isFailed) {
    borderClass = "border-[#EF4444]/60 shadow-[0_0_15px_rgba(239,68,68,0.2)]";
    bgClass = "bg-[#251517]/80";
    statusBadge = (
      <span className="flex items-center gap-1 text-[11px] font-medium text-[#EF4444] bg-[#EF4444]/10 px-2 py-0.5 rounded-full border border-[#EF4444]/20">
        <AlertCircle className="w-3 h-3" />
        Failed
      </span>
    );
  } else {
    statusBadge = (
      <span className="flex items-center gap-1 text-[11px] font-medium text-[#6B7280] bg-[#1F2430] px-2 py-0.5 rounded-full">
        <Clock className="w-3 h-3" />
        Waiting
      </span>
    );
  }

  return (
    <div
      className={`min-w-[240px] max-w-[280px] rounded-xl border backdrop-blur-md p-4 transition-all duration-300 ${borderClass} ${bgClass}`}
    >
      <Handle
        type="target"
        position={Position.Top}
        className="!bg-[#FED766] !w-2.5 !h-2.5 !border-2 !border-[#0E1015]"
      />

      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="flex items-center gap-2.5">
          <div
            className={`w-8 h-8 rounded-lg flex items-center justify-center ${
              isRunning
                ? "bg-[#FED766]/20 text-[#FED766]"
                : isCompleted
                ? "bg-[#10B981]/20 text-[#10B981]"
                : isFailed
                ? "bg-[#EF4444]/20 text-[#EF4444]"
                : "bg-[#222836] text-[#9CA3AF]"
            }`}
          >
            <Icon className="w-4 h-4" />
          </div>
          <div>
            <h4 className="text-sm font-semibold text-white tracking-tight">{data.label}</h4>
            {data.sublabel && (
              <p className="text-[11px] text-[#9CA3AF] leading-none mt-0.5">{data.sublabel}</p>
            )}
          </div>
        </div>

        {statusBadge}
      </div>

      {data.message && (
        <p className="text-xs text-[#D1D5DB] bg-black/30 rounded-lg p-2 border border-white/5 line-clamp-2 mt-2">
          {data.message}
        </p>
      )}

      {data.badge && (
        <div className="mt-2.5 flex items-center gap-1.5 text-[10px] text-[#9CA3AF]">
          <span className="w-1.5 h-1.5 rounded-full bg-[#FED766]" />
          <span>{data.badge}</span>
        </div>
      )}

      <Handle
        type="source"
        position={Position.Bottom}
        className="!bg-[#FED766] !w-2.5 !h-2.5 !border-2 !border-[#0E1015]"
      />
    </div>
  );
}
