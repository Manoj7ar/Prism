import React, { useEffect, useState, useCallback, useRef } from "react";

const BACKEND_URL = "http://localhost:8000";

export function WeatherTime() {
  const [time, setTime] = useState<string>("");

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setTime(now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }));
    };

    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex items-center gap-2.5 px-4 py-1.5 bg-black rounded-full border border-white/10 text-[11px] font-bold text-white group relative">
      <span className="tracking-tighter opacity-90">{time}</span>
    </div>
  );
}

export function ContextCircle({ tokens }: { tokens: number }) {
  const MAX_TOKENS = 1000000;
  const percentage = Math.min((tokens / MAX_TOKENS) * 100, 100);
  const radius = 10;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (percentage / 100) * circumference;

  return (
    <div className="relative flex items-center justify-center w-8 h-8 group cursor-default">
      <svg className="w-6 h-6 transform -rotate-90">
        <circle
          cx="12"
          cy="12"
          r={radius}
          stroke="currentColor"
          strokeWidth="2.5"
          fill="transparent"
          className="text-white/10"
        />
        <circle
          cx="12"
          cy="12"
          r={radius}
          stroke="currentColor"
          strokeWidth="2.5"
          fill="transparent"
          strokeDasharray={circumference}
          style={{ 
            strokeDashoffset,
            transition: 'stroke-dashoffset 0.8s cubic-bezier(0.4, 0, 0.2, 1)',
          }}
          strokeLinecap="round"
          className="text-[#00FF9D]"
        />
      </svg>
      
      <div className="absolute bottom-full mb-3 opacity-0 group-hover:opacity-100 transition-all duration-200 transform translate-y-2 group-hover:translate-y-0 bg-black border border-white/10 p-3 rounded-2xl z-50 pointer-events-none min-w-[160px] right-0 translate-x-[20%]">
        <div className="text-[10px] font-bold text-white/40 uppercase tracking-[0.1em] mb-1.5 text-left">Context Window</div>
        <div className="flex justify-between items-baseline mb-2">
          <span className="text-[13px] text-white font-mono font-bold">{(tokens / 1000).toFixed(1)}k</span>
          <span className="text-[10px] text-white/30 font-medium">/ 1M tokens</span>
        </div>
        <div className="w-full bg-white/5 h-1.5 rounded-full overflow-hidden">
          <div 
            className="bg-[#00FF9D] h-full" 
            style={{ width: `${percentage}%` }}
          />
        </div>
        <div className="mt-2 text-[9px] text-[#00FF9D]/60 font-medium italic text-left">
          {percentage.toFixed(1)}% Capacity Used
        </div>
      </div>
    </div>
  );
}

interface VisualMemoryStatus {
  success: boolean;
  is_recording?: boolean;
  is_paused?: boolean;
  is_disabled?: boolean;
  recording?: boolean;
  frame_count?: number;
  elapsed_seconds?: number;
  duration_minutes?: number;
  max_minutes?: number;
  seconds_remaining?: number;
  storage_mb?: number;
  max_storage_mb?: number;
  capture_interval_seconds?: number;
}

export function VisualMemoryCircle() {
  const [status, setStatus] = useState<VisualMemoryStatus | null>(null);
  const [captureCyclePercent, setCaptureCyclePercent] = useState<number>(0);
  const [lastCaptureTs, setLastCaptureTs] = useState<number>(Date.now());
  const [wipeFlashUntil, setWipeFlashUntil] = useState<number>(0);
  const prevStatusRef = useRef<VisualMemoryStatus | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/memory-status`);
      const data = await res.json();
      if (data?.success) {
        const prev = prevStatusRef.current;
        // Detect memory window reset or storage wipe.
        const secondsRemaining = Number(data.seconds_remaining ?? 0);
        const prevSecondsRemaining = Number(prev?.seconds_remaining ?? 0);
        const storageMb = Number(data.storage_mb ?? 0);
        const prevStorageMb = Number(prev?.storage_mb ?? 0);
        const frameCount = Number(data.frame_count ?? 0);
        const prevFrameCount = Number(prev?.frame_count ?? 0);

        const resetByTime = prev && secondsRemaining > prevSecondsRemaining + 5;
        const resetByStorage = prev && storageMb < prevStorageMb - 1;
        const resetByFrames = prev && prevFrameCount > 0 && frameCount === 0;

        if (resetByTime || resetByStorage || resetByFrames) {
          const now = Date.now();
          setWipeFlashUntil(now + 800);
          setCaptureCyclePercent(100);
          setLastCaptureTs(now);
        }

        setStatus(data);
        prevStatusRef.current = data;
      }
    } catch (e) {}
  }, []);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 5000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  useEffect(() => {
    const eventSource = new EventSource(`${BACKEND_URL}/screenshot/events`);
    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data?.type === "screenshot") {
          setLastCaptureTs(Date.now());
          setCaptureCyclePercent(0);
        }
      } catch {}
    };
    eventSource.onerror = () => {
      eventSource.close();
    };
    return () => eventSource.close();
  }, []);

  useEffect(() => {
    const ticker = setInterval(() => {
      const intervalSec = Math.max(1, status?.capture_interval_seconds ?? 15);
      const active = !!status?.recording && !status?.is_disabled;
      const now = Date.now();
      if (wipeFlashUntil > now) {
        setCaptureCyclePercent(100);
        return;
      }
      if (!active) {
        setCaptureCyclePercent(0);
        return;
      }
      const elapsed = (now - lastCaptureTs) / 1000;
      const pct = Math.max(0, Math.min((elapsed / intervalSec) * 100, 100));
      setCaptureCyclePercent(pct);
    }, 100);

    return () => clearInterval(ticker);
  }, [status?.capture_interval_seconds, status?.recording, status?.is_disabled, lastCaptureTs, wipeFlashUntil]);

  const disabled = !!status?.is_disabled;
  const active = !!status?.recording && !disabled;
  const duration = status?.duration_minutes ?? Math.floor((status?.elapsed_seconds ?? 0) / 60);
  const maxMinutes = Math.max(1, status?.max_minutes ?? 180);
  const percentage = active ? captureCyclePercent : Math.max(0, Math.min((duration / maxMinutes) * 100, 100));

  const radius = 10;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (percentage / 100) * circumference;

  return (
    <div className="relative flex items-center justify-center w-8 h-8 group cursor-default">
      <svg className="w-6 h-6 transform -rotate-90">
        <circle
          cx="12"
          cy="12"
          r={radius}
          stroke="currentColor"
          strokeWidth="2.5"
          fill="transparent"
          className="text-white/10"
        />
        {disabled ? (
          <>
            <circle
              cx="12"
              cy="12"
              r={radius}
              stroke="currentColor"
              strokeWidth="2.5"
              fill="transparent"
              className="text-red-500/80"
            />
            <line
              x1="6.5"
              y1="17.5"
              x2="17.5"
              y2="6.5"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
              className="text-red-400"
            />
          </>
        ) : (
          <circle
            cx="12"
            cy="12"
            r={radius}
            stroke="currentColor"
            strokeWidth="2.5"
            fill="transparent"
            strokeDasharray={circumference}
            style={{
              strokeDashoffset,
              transition: active ? 'stroke-dashoffset 120ms linear' : 'stroke-dashoffset 0.8s cubic-bezier(0.4, 0, 0.2, 1)',
            }}
            strokeLinecap="round"
            className={active ? "text-[#00FF9D]" : "text-white/30"}
          />
        )}
      </svg>

      {disabled && (
        <div className="absolute inset-0 rounded-full shadow-[0_0_12px_rgba(255,80,80,0.25)]" />
      )}

      <div className="absolute bottom-full mb-3 opacity-0 group-hover:opacity-100 transition-all duration-200 transform translate-y-2 group-hover:translate-y-0 bg-black border border-white/10 pt-3.5 pb-3 px-3 rounded-[18px] z-50 pointer-events-none min-w-[200px] right-0 translate-x-[20%] overflow-visible">
        <div className="text-[10px] leading-none font-bold text-white/40 uppercase tracking-[0.1em] mb-2 text-left">Visual Memory</div>
        <div className="text-[11px] text-white/80 text-left mb-2">
          {disabled ? "OFF" : active ? "ON" : "Paused"}
        </div>
        <div className="grid grid-cols-2 gap-y-1 gap-x-3 text-[10px] text-white/60">
          <span>Frames</span><span className="text-white/85">{status?.frame_count ?? 0}</span>
          <span>Capture gap</span><span className="text-white/85">{status?.capture_interval_seconds ?? 15}s</span>
          <span>Used</span><span className="text-white/85">{duration}m / {maxMinutes}m</span>
          <span>Storage</span><span className="text-white/85">{status?.storage_mb ?? 0}MB / {status?.max_storage_mb ?? 500}MB</span>
        </div>
      </div>
    </div>
  );
}

export function TokenUsage() {
  const [tokens, setTokens] = useState<number>(0);
  const MAX_TOKENS = 1000000;

  const fetchTokens = useCallback(async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/tokens`);
      const data = await res.json();
      if (data.success) setTokens(data.total_tokens);
    } catch (e) {}
  }, []);

  useEffect(() => {
    fetchTokens();
    const interval = setInterval(fetchTokens, 15000);
    return () => clearInterval(interval);
  }, [fetchTokens]);

  return <ContextCircle tokens={tokens} />;
}
