"use client";

import React, { useRef, useEffect } from "react";
import { ActivityMessage } from "@/lib/types";
import { Info, CheckCircle2, AlertTriangle, AlertCircle, Radio } from "lucide-react";

interface ActivityFeedProps {
  messages: ActivityMessage[];
  connected: boolean;
}

export function ActivityFeed({ messages, connected }: ActivityFeedProps) {
  const feedRef = useRef<HTMLDivElement>(null);

  const getBadge = (type: ActivityMessage["type"]) => {
    switch (type) {
      case "success":
        return <CheckCircle2 className="w-3.5 h-3.5 text-[#10B981] shrink-0 mt-0.5" />;
      case "warning":
        return <AlertTriangle className="w-3.5 h-3.5 text-[#F59E0B] shrink-0 mt-0.5" />;
      case "error":
        return <AlertCircle className="w-3.5 h-3.5 text-[#EF4444] shrink-0 mt-0.5" />;
      default:
        return <Info className="w-3.5 h-3.5 text-[#FED766] shrink-0 mt-0.5" />;
    }
  };

  const formatTime = (ts: number) => {
    const d = new Date(ts);
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  };

  return (
    <div className="w-full h-full flex flex-col rounded-2xl glass-panel border border-white/5 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/5 bg-black/20">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-white tracking-wide uppercase">
            Activity Feed
          </span>
          <span className="text-[10px] text-[#9CA3AF] bg-[#222836] px-1.5 py-0.5 rounded-full font-mono">
            {messages.length}
          </span>
        </div>

        <div className="flex items-center gap-1.5 text-[11px]">
          <span
            className={`w-2 h-2 rounded-full ${
              connected ? "bg-[#10B981] animate-pulse" : "bg-[#EF4444]"
            }`}
          />
          <span className="text-[#9CA3AF] font-medium">
            {connected ? "Live Stream" : "Connecting..."}
          </span>
        </div>
      </div>

      {/* Message List */}
      <div
        ref={feedRef}
        className="flex-1 overflow-y-auto p-3 space-y-2 font-sans text-xs scroll-smooth"
      >
        {messages.length === 0 ? (
          <div className="h-full flex items-center justify-center text-center text-[#6B7280] py-8">
            Waiting for pipeline events...
          </div>
        ) : (
          messages.map((m) => (
            <div
              key={m.id}
              className="p-2.5 rounded-xl glass-card border border-white/[0.04] hover:border-white/10 transition-colors flex items-start gap-2.5"
            >
              {getBadge(m.type)}
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-2 mb-1">
                  <span className="text-[10px] font-semibold text-[#FED766] uppercase tracking-wider">
                    {m.stage}
                  </span>
                  <span className="text-[10px] text-[#6B7280] font-mono">
                    {formatTime(m.timestamp)}
                  </span>
                </div>
                <p className="text-[#D1D5DB] leading-relaxed break-words">{m.message}</p>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
