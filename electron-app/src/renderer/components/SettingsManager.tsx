import React, { useState, useEffect } from "react";
import { X, RefreshCcw, Shield, Cpu, Loader2, CheckCircle2, Eye, Zap, Command } from "lucide-react";
import { motion } from "framer-motion";
import { cn } from "../lib/utils";
import { PrismIcon } from "./ui/PrismIcon";

interface SettingsManagerProps {
  onClose: () => void;
  onResetHistory: () => void;
}

const BACKEND_URL = "http://localhost:8000";

export default function SettingsManager({ onClose, onResetHistory }: SettingsManagerProps) {
  const [isClearingMemory, setIsClearingMemory] = useState(false);
  const [clearedSuccess, setClearedSuccess] = useState(false);
  const [privacyMode, setPrivacyMode] = useState(false);
  const [fastModeEnabled, setFastModeEnabled] = useState(true);
  const [isTogglingFastMode, setIsTogglingFastMode] = useState(false);

  useEffect(() => {
    fetchPrivacyStatus();
    fetchAppSettings();
  }, []);

  const fetchAppSettings = async () => {
    try {
      const response = await fetch(`${BACKEND_URL}/settings`);
      const data = await response.json();
      if (data.success) {
        setFastModeEnabled(!!data.fast_mode_enabled);
      }
    } catch (e) {}
  };

  const fetchPrivacyStatus = async () => {
    try {
      const response = await fetch(`${BACKEND_URL}/memory-status`);
      const data = await response.json();
      if (data.success) setPrivacyMode(!!data.is_disabled);
    } catch (e) {}
  };

  const handleTogglePrivacy = async (value: boolean) => {
    const previous = privacyMode;
    setPrivacyMode(value);
    try {
      await fetch(`${BACKEND_URL}/memory-toggle`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ disabled: value })
      });
      await fetchPrivacyStatus();
    } catch (e) {
      setPrivacyMode(previous);
    }
  };

  const handleToggleFastMode = async (enabled: boolean) => {
    if (isTogglingFastMode || enabled === fastModeEnabled) return;
    const previous = fastModeEnabled;
    setFastModeEnabled(enabled);
    setIsTogglingFastMode(true);
    try {
      await fetch(`${BACKEND_URL}/settings/fast-mode`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled })
      });
    } catch (e) {
      setFastModeEnabled(previous);
    } finally {
      setIsTogglingFastMode(false);
    }
  };

  const handleClearMemory = async () => {
    setIsClearingMemory(true);
    try {
      await fetch(`${BACKEND_URL}/memory-clear`, { method: "POST" });
      setClearedSuccess(true);
      setTimeout(() => setClearedSuccess(false), 2000);
    } catch (e) {} finally {
      setIsClearingMemory(false);
    }
  };


  const springConfig = { type: "spring" as const, damping: 26, stiffness: 320, mass: 0.9 };
  const cardClass = "rounded-2xl bg-black/80 border border-white/5";
  const sectionTitleClass = "text-[11px] font-semibold uppercase tracking-[0.18em] text-white/45";

  return (
    <motion.div
      initial={{ opacity: 0, y: 10, scale: 0.985 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 8, scale: 0.98 }}
      transition={{ duration: 0.34, ease: [0.22, 1, 0.36, 1] }}
      className="relative flex flex-col h-full rounded-[26px] overflow-hidden bg-black shadow-[0_24px_70px_-36px_rgba(0,0,0,0.95)]"
    >
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(255,255,255,0.08),_transparent_55%)] pointer-events-none" />
      <div className="absolute inset-x-0 top-0 h-24 bg-gradient-to-b from-white/[0.06] to-transparent pointer-events-none" />
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.24, delay: 0.05 }}
        className="relative z-10 flex items-center justify-between px-5 pt-4 pb-3 border-b border-white/10 rounded-t-[26px] overflow-hidden"
      >
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-2xl bg-white/[0.06] border border-white/10 flex items-center justify-center">
            <PrismIcon className="w-4.5 h-4.5 text-white" />
          </div>
          <div className="leading-tight">
            <p className="text-[15px] font-semibold text-white">Prism</p>
            <p className="text-[10px] uppercase tracking-[0.18em] text-white/45">Settings</p>
          </div>
        </div>
        <button
          onClick={onClose} 
          className="p-2 rounded-xl bg-white/[0.04] hover:bg-white/[0.08] text-white/60 hover:text-white transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </motion.div>

      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.26, delay: 0.09 }}
        className="relative z-10 flex-1 px-5 py-4 grid grid-rows-[auto_auto_1fr] gap-3 min-h-0"
      >
        <section className="grid grid-cols-2 gap-2.5">
          <div className={cn(cardClass, "px-3 py-2.5")}>
            <p className="text-[10px] uppercase tracking-[0.14em] text-white/40">Incognito</p>
            <p className="text-xs font-medium text-white mt-1">{privacyMode ? "Enabled" : "Disabled"}</p>
          </div>
          <div className={cn(cardClass, "px-3 py-2.5")}>
            <p className="text-[10px] uppercase tracking-[0.14em] text-white/40">Performance</p>
            <p className="text-xs font-medium text-white mt-1">{fastModeEnabled ? "Fast Mode" : "Balanced Mode"}</p>
          </div>
        </section>

        <section className={cn(cardClass, "p-3 grid gap-2.5")}>
          <p className={sectionTitleClass}>Runtime Controls</p>
          <div className="rounded-xl bg-white/[0.03] px-3 py-2.5 flex items-center justify-between border border-white/5">
            <div className="flex items-center gap-2.5">
              <div className={cn("p-2 rounded-lg", privacyMode ? "text-white bg-white/12" : "text-white/50 bg-white/[0.04]")}>
                {privacyMode ? <Eye className="w-4 h-4" /> : <Shield className="w-4 h-4" />}
              </div>
              <div>
                <p className="text-sm font-medium text-white">Incognito Mode</p>
                <p className="text-[11px] text-white/45">Stops capture and session learning</p>
              </div>
            </div>
            <button 
              onClick={() => handleTogglePrivacy(!privacyMode)}
              className={cn("w-11 h-6 rounded-full transition-all relative p-0.5", privacyMode ? "bg-white/70" : "bg-white/10")}
            >
              <motion.div
                layout
                transition={springConfig}
                className="w-5 h-5 rounded-full bg-white"
                animate={{ x: privacyMode ? 20 : 0 }}
              />
            </button>
          </div>

          <div className="rounded-xl bg-white/[0.03] px-3 py-2.5 flex items-center justify-between border border-white/5">
            <div className="flex items-center gap-2.5">
              <div className={cn("p-2 rounded-lg", fastModeEnabled ? "text-white bg-white/12" : "text-white/50 bg-white/[0.04]")}>
                <Zap className="w-4 h-4" />
              </div>
              <div>
                <p className="text-sm font-medium text-white">Fast Mode</p>
                <p className="text-[11px] text-white/45">Faster replies, less analysis overhead</p>
              </div>
            </div>
            <button
              onClick={() => handleToggleFastMode(!fastModeEnabled)}
              disabled={isTogglingFastMode}
              className={cn("w-11 h-6 rounded-full transition-all relative p-0.5 disabled:opacity-60", fastModeEnabled ? "bg-white/70" : "bg-white/10")}
            >
              <motion.div
                layout
                transition={springConfig}
                className="w-5 h-5 rounded-full bg-white flex items-center justify-center"
                animate={{ x: fastModeEnabled ? 20 : 0 }}
              >
                {isTogglingFastMode && <Loader2 className="w-3 h-3 text-black animate-spin" />}
              </motion.div>
            </button>
          </div>
        </section>

        <section className="grid grid-cols-1 gap-2.5">
          <button 
            onClick={handleClearMemory}
            disabled={isClearingMemory || clearedSuccess}
            className={cn(cardClass, "hover:bg-white/[0.06] px-3 py-3 transition-colors text-left")}
          >
            <div className="flex items-center gap-2">
              {isClearingMemory ? <Loader2 className="w-4 h-4 animate-spin text-white/80" /> : clearedSuccess ? <CheckCircle2 className="w-4 h-4 text-white" /> : <RefreshCcw className="w-4 h-4 text-white/80" />}
              <p className="text-sm font-medium text-white">Clear Visual Memory</p>
            </div>
            <p className="text-[11px] text-white/45 mt-1">Deletes all captured screenshots and resets the memory window</p>
          </button>
        </section>

        <section className={cn(cardClass, "px-3 py-2.5")}>
          <div className="flex items-center gap-2 mb-1.5">
            <Command className="w-3.5 h-3.5 text-white/70" />
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-white/50">Shortcuts</p>
          </div>
          <div className="grid grid-cols-2 gap-1.5 text-[11px]">
            <div className="rounded-md bg-white/[0.04] px-2 py-1 text-white/70 border border-white/5"><kbd className="text-white">Alt+Space</kbd> Show/Hide</div>
            <div className="rounded-md bg-white/[0.04] px-2 py-1 text-white/70 border border-white/5"><kbd className="text-white">Alt+C</kbd> Reset Session</div>
          </div>
        </section>
      </motion.div>

      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.2, delay: 0.12 }}
        className="relative z-10 px-5 py-3 bg-black border-t border-white/10 flex items-center justify-between"
      >
        <div className="flex items-center gap-3">
          <div className="w-1.5 h-1.5 rounded-full bg-white/80" />
          <span className="text-[9px] text-white/30 font-semibold uppercase tracking-[0.2em]">System Online</span>
        </div>
        <div className="flex items-center gap-2">
          <Cpu className="w-3 h-3 text-white/20" />
          <p className="text-[9px] text-white/20 font-semibold uppercase tracking-[0.2em]">Prism v2.0.4</p>
        </div>
      </motion.div>
    </motion.div>
  );
}
