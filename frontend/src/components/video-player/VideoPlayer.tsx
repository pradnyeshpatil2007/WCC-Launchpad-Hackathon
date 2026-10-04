"use client";

import React, { useRef, useState, useEffect } from "react";
import {
  Play,
  Pause,
  Volume2,
  VolumeX,
  Maximize2,
  Download,
  Share2,
  RotateCcw,
  Sparkles,
} from "lucide-react";
import { api } from "@/lib/api";

interface VideoPlayerProps {
  jobId: string;
  title?: string | null;
  durationSec?: number | null;
  sceneStartTimes?: number[] | null;
  seekTime?: number;
}

export function VideoPlayer({
  jobId,
  title,
  durationSec = 60,
  sceneStartTimes,
  seekTime,
}: VideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [currentTime, setCurrentTime] = useState<number>(0);
  const [videoDuration, setVideoDuration] = useState<number>(durationSec || 60);
  const [isMuted, setIsMuted] = useState<boolean>(false);
  const [volume, setVolume] = useState<number>(1.0);
  const [copied, setCopied] = useState<boolean>(false);

  const videoUrl = api.getVideoUrl(jobId);
  const thumbnailUrl = api.getThumbnailUrl(jobId);

  useEffect(() => {
    if (seekTime !== undefined && videoRef.current) {
      videoRef.current.currentTime = seekTime;
      if (!isPlaying) {
        videoRef.current.play().catch(() => {});
        setIsPlaying(true);
      }
    }
  }, [seekTime]);

  const togglePlay = () => {
    if (!videoRef.current) return;
    if (isPlaying) {
      videoRef.current.pause();
      setIsPlaying(false);
    } else {
      videoRef.current.play().catch(() => {});
      setIsPlaying(true);
    }
  };

  const toggleMute = () => {
    if (!videoRef.current) return;
    videoRef.current.muted = !isMuted;
    setIsMuted(!isMuted);
  };

  const handleTimeUpdate = () => {
    if (!videoRef.current) return;
    setCurrentTime(videoRef.current.currentTime);
  };

  const handleLoadedMetadata = () => {
    if (!videoRef.current) return;
    setVideoDuration(videoRef.current.duration || durationSec || 60);
  };

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const time = parseFloat(e.target.value);
    setCurrentTime(time);
    if (videoRef.current) {
      videoRef.current.currentTime = time;
    }
  };

  const toggleFullscreen = () => {
    if (!containerRef.current) return;
    if (document.fullscreenElement) {
      document.exitFullscreen();
    } else {
      containerRef.current.requestFullscreen();
    }
  };

  const handleCopyLink = () => {
    navigator.clipboard.writeText(window.location.href);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs < 10 ? "0" : ""}${secs}`;
  };

  return (
    <div
      ref={containerRef}
      className="flex flex-col items-center justify-center w-full max-w-sm mx-auto"
    >
      {/* 9:16 Vertical Video Frame */}
      <div className="relative w-full aspect-[9/16] rounded-2xl overflow-hidden shadow-2xl border border-white/10 bg-black group">
        <video
          ref={videoRef}
          src={videoUrl}
          poster={thumbnailUrl}
          playsInline
          onTimeUpdate={handleTimeUpdate}
          onLoadedMetadata={handleLoadedMetadata}
          onEnded={() => setIsPlaying(false)}
          onClick={togglePlay}
          className="w-full h-full object-cover cursor-pointer"
        />

        {/* Big Center Play Button when paused */}
        {!isPlaying && (
          <button
            onClick={togglePlay}
            className="absolute inset-0 m-auto w-16 h-16 rounded-full bg-[#FED766]/90 text-black flex items-center justify-center shadow-lg transition-transform hover:scale-110 active:scale-95 z-20 backdrop-blur-sm"
          >
            <Play className="w-8 h-8 fill-black translate-x-0.5" />
          </button>
        )}

        {/* Video Controls Overlay */}
        <div className="absolute inset-x-0 bottom-0 p-4 bg-gradient-to-t from-black/90 via-black/50 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300 flex flex-col gap-2 z-30">
          {/* Progress scrubber */}
          <div className="relative w-full flex items-center">
            <input
              type="range"
              min={0}
              max={videoDuration || 60}
              step={0.1}
              value={currentTime}
              onChange={handleSeek}
              className="w-full h-1.5 bg-white/20 rounded-lg appearance-none cursor-pointer accent-[#FED766]"
            />
          </div>

          {/* Buttons row */}
          <div className="flex items-center justify-between text-white text-xs">
            <div className="flex items-center gap-3">
              <button
                onClick={togglePlay}
                className="hover:text-[#FED766] transition-colors"
              >
                {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4 fill-white" />}
              </button>

              <button
                onClick={toggleMute}
                className="hover:text-[#FED766] transition-colors"
              >
                {isMuted ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4" />}
              </button>

              <span className="font-mono text-[11px] text-[#D1D5DB]">
                {formatTime(currentTime)} / {formatTime(videoDuration)}
              </span>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={toggleFullscreen}
                className="hover:text-[#FED766] transition-colors"
                title="Fullscreen"
              >
                <Maximize2 className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Action buttons bar */}
      <div className="flex items-center justify-center gap-3 mt-4 w-full">
        <a
          href={videoUrl}
          download={`${jobId}-autoshorts.mp4`}
          className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-[#FED766] text-black font-semibold text-xs shadow-lg hover:bg-[#FDE047] transition-all"
        >
          <Download className="w-4 h-4" />
          <span>Download MP4</span>
        </a>

        <button
          onClick={handleCopyLink}
          className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl glass-card text-white hover:border-white/20 transition-all text-xs font-medium"
        >
          <Share2 className="w-4 h-4 text-[#FED766]" />
          <span>{copied ? "Copied!" : "Share Link"}</span>
        </button>
      </div>
    </div>
  );
}
