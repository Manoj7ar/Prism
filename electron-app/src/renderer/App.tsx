import React, { useState, useEffect, useCallback, useRef } from "react";
import { AIInputWithFile } from "./components/ui/AIInputWithFile";
import { cn } from "./lib/utils";
import { motion, AnimatePresence, LayoutGroup, Variants } from "framer-motion";
import SummaryView from "./components/SummaryView";
import PresetManager from "./components/PresetManager";
import SettingsManager from "./components/SettingsManager";
import { PrismIcon } from "./components/ui/PrismIcon";
import ApiKeyModal from "./components/ApiKeyModal";
import { Plus, RotateCcw } from "lucide-react";


type AnimationPhase = 'hidden' | 'logo-only' | 'expanded' | 'collapsing';

const BACKEND_URL = "http://localhost:8000";

interface HistoryItem {
  role: 'user' | 'assistant';
  content: string;
  source_url?: string;
}

const isOpenCommand = (message: string) => /^\s*open\b/i.test(message);
const isBankOpenCommand = (message: string) => {
  if (!isOpenCommand(message)) return false;
  const text = message.toLowerCase();
  const bankKeywords = [
    "bank",
    "banking",
    "netbanking",
    "online banking",
    "bank of america",
    "wells fargo",
    "chase",
    "citibank",
    "citi",
    "capital one",
    "hsbc",
    "barclays",
    "icici",
    "hdfc",
    "sbi",
    "axis bank",
    "kotak",
  ];
  return bankKeywords.some((k) => text.includes(k));
};

export default function App() {
  const queryParams = new URLSearchParams(window.location.search);
  const isSummaryMode = queryParams.get('mode') === 'summary';
  const isOverlayMode = queryParams.get('mode') === 'overlay';

  const [isVisible, setIsVisible] = useState(true);
  const [animationPhase, setAnimationPhase] = useState<AnimationPhase>('expanded');
  const [isProcessing, setIsProcessing] = useState(false);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [resetKey, setResetKey] = useState(0);
  const [isWiping, setIsWiping] = useState(false);
  const [activeApp, setActiveApp] = useState<string>("Desktop");
  const [showPresets, setShowPresets] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [authNeeded, setAuthNeeded] = useState(false);
  const [isGlowActive, setIsGlowActive] = useState(false);
  const [openTaskFlowActive, setOpenTaskFlowActive] = useState(false);
  const [openTaskPillVisible, setOpenTaskPillVisible] = useState(false);
  const [openTaskLabel, setOpenTaskLabel] = useState("");
  const openTaskStartedAtRef = useRef<number>(0);
  const openTaskCloseTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const lastSpacePress = useRef<number>(0);
  const spacePressCount = useRef<number>(0);
  const hideTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const springConfig = { type: "spring" as const, damping: 25, stiffness: 350, mass: 1 };
  const containerVariants: Variants = {
    hidden: {
      opacity: 0
    },
    visible: {
      opacity: 1,
      transition: {
        duration: 0.26,
        ease: [0.22, 1, 0.36, 1]
      }
    },
    exit: {
      opacity: 0,
      transition: {
        duration: 0.34,
        ease: [0.4, 0, 0.2, 1]
      }
    }
  };

  const checkAuth = useCallback(async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/check-auth`);
      const data = await res.json();
      if (data.authenticated === false) {
        setAuthNeeded(true);
      } else {
        setAuthNeeded(false);
      }
    } catch (e) {
      console.error("Auth check failed:", e);
    }
  }, []);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  const fetchActiveApp = useCallback(async () => {
    try {
      const response = await fetch(`${BACKEND_URL}/active-app`);
      if (!response.ok) return;
      const data = await response.json();
      if (data.success && data.app_name !== activeApp) {
        setActiveApp(data.app_name);
      }
    } catch (e) {
      console.error("App fetch failed:", e);
    }
  }, [activeApp]);

  const handleReset = useCallback(async () => {
    setIsWiping(true);
    await new Promise(r => setTimeout(r, 300));

    try {
      await fetch(`${BACKEND_URL}/reset`, { method: 'POST' });
    } catch (e) {
      console.error("Reset failed:", e);
    } finally {
      setHistory([]);
      setIsProcessing(false);
      setOpenTaskFlowActive(false);
      setOpenTaskPillVisible(false);
      setOpenTaskLabel("");
      if (window.electron?.showAutomationOverlay) {
        window.electron.showAutomationOverlay(false).catch(() => {});
      }
      if (openTaskCloseTimerRef.current) {
        clearTimeout(openTaskCloseTimerRef.current);
        openTaskCloseTimerRef.current = null;
      }
      setResetKey(prev => prev + 1);
      if (window.electron) window.electron.resizeWindow(370, 220);
      setIsWiping(false);
    }
  }, []);

  const handleKill = useCallback(async () => {
    try {
      await fetch(`${BACKEND_URL}/reset`, { method: 'POST' });
      if (window.electron) await window.electron.hideWindow();
      setIsProcessing(false);
      setHistory([]);
      setOpenTaskFlowActive(false);
      setOpenTaskPillVisible(false);
      setOpenTaskLabel("");
      if (window.electron?.showAutomationOverlay) {
        window.electron.showAutomationOverlay(false).catch(() => {});
      }
      if (openTaskCloseTimerRef.current) {
        clearTimeout(openTaskCloseTimerRef.current);
        openTaskCloseTimerRef.current = null;
      }
      setResetKey(prev => prev + 1);
    } catch (e) {
      console.error("Kill failed:", e);
    }
  }, []);

  const closeOpenTaskFlow = useCallback(() => {
    const MIN_PILL_VISIBLE_MS = 700;
    const elapsed = Date.now() - openTaskStartedAtRef.current;
    const wait = Math.max(0, MIN_PILL_VISIBLE_MS - elapsed);

    if (openTaskCloseTimerRef.current) {
      clearTimeout(openTaskCloseTimerRef.current);
    }
    openTaskCloseTimerRef.current = setTimeout(() => {
      setOpenTaskPillVisible(false);
      if (window.electron?.showAutomationOverlay) {
        window.electron.showAutomationOverlay(false).catch(() => {});
      }
      setTimeout(() => setOpenTaskFlowActive(false), 260);
      openTaskCloseTimerRef.current = null;
    }, wait);
  }, []);

  const handleRunPreset = useCallback(async (preset: any) => {
    setIsProcessing(true);
    setShowPresets(false);
    const newHistory = [...history, { role: 'user' as const, content: `Workflow: ${preset.name}` }];
    setHistory(newHistory);

    try {
      if (window.electron) {
        const result = await window.electron.executePreset(preset.steps, newHistory);
        setIsProcessing(false);
        if (result.reply) setHistory(prev => [...prev, { role: 'assistant', content: result.reply }]);
      }
    } catch (error) {
      console.error("Preset error:", error);
      setIsProcessing(false);
    }
  }, [history]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.altKey && e.code === 'KeyC') { e.preventDefault(); handleReset(); }
      if (e.altKey && e.code === 'Space') {
        const now = Date.now();
        if (now - lastSpacePress.current < 500) spacePressCount.current += 1;
        else spacePressCount.current = 1;
        lastSpacePress.current = now;
        if (spacePressCount.current === 2) { handleReset(); spacePressCount.current = 0; return; }
        if (isProcessing) handleKill();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isProcessing, handleKill, handleReset]);

  const handleSubmit = useCallback(async (message: string, file?: File) => {
    const isOpen = isOpenCommand(message);
    const isBankOpen = isBankOpenCommand(message);

    if (isOpen && isBankOpen) {
      setIsProcessing(false);
      setOpenTaskFlowActive(true);
      setOpenTaskLabel("Can't open bank or banking websites.");
      setOpenTaskPillVisible(true);
      if (window.electron?.showAutomationOverlay) {
        window.electron.showAutomationOverlay(false).catch(() => {});
      }
      if (openTaskCloseTimerRef.current) {
        clearTimeout(openTaskCloseTimerRef.current);
      }
      openTaskCloseTimerRef.current = setTimeout(() => {
        setOpenTaskPillVisible(false);
        setTimeout(() => setOpenTaskFlowActive(false), 260);
        openTaskCloseTimerRef.current = null;
      }, 1700);
      return;
    }

    setIsProcessing(true);
    setOpenTaskFlowActive(isOpen);
    if (isOpen) {
      openTaskStartedAtRef.current = Date.now();
      setOpenTaskLabel(message.trim());
      setOpenTaskPillVisible(true);
      if (window.electron?.showAutomationOverlay) {
        window.electron.showAutomationOverlay(true).catch(() => {});
      }
    } else {
      setOpenTaskPillVisible(false);
      setOpenTaskLabel("");
      if (window.electron?.showAutomationOverlay) {
        window.electron.showAutomationOverlay(false).catch(() => {});
      }
    }

    const currentHistory = isOpen
      ? [...history]
      : [...history, { role: 'user' as const, content: message }];
    if (!isOpen) {
      setHistory(currentHistory);
    }

    try {
      const formData = new FormData();
      formData.append('command', message);
      formData.append('history', JSON.stringify(currentHistory));
      if (file) formData.append('file', file);

      const response = await fetch(`${BACKEND_URL}/execute-stream`, { method: 'POST', body: formData });
      if (!response.body) throw new Error("No body");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let assistantReply = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const dataStr = line.slice(6).trim();
            if (!dataStr) continue;
            const data = JSON.parse(dataStr);
            if (data.type === 'reply_start') {
              if (!isOpen) {
                setHistory(prev => [...prev, { role: 'assistant', content: "" }]);
              }
            } else if (data.type === 'tasks') {
              if (isOpen) {
                const tasks = Array.isArray(data.tasks) ? data.tasks : [];
                const activeTask = tasks.find((t: any) => t.status === "in_progress") || tasks.find((t: any) => t.status === "pending");
                if (activeTask?.label) {
                  setOpenTaskLabel(String(activeTask.label));
                  setOpenTaskPillVisible(true);
                }
              }
            } else if (data.type === 'reply_chunk') {
              if (!isOpen) {
                assistantReply += data.content;
                setHistory(prev => {
                  const newHist = [...prev];
                  if (newHist.length > 0 && newHist[newHist.length - 1].role === 'assistant') {
                    newHist[newHist.length - 1].content = assistantReply;
                  }
                  return newHist;
                });
              }
            } else if (data.type === 'done') {
              setIsProcessing(false);
              if (isOpen) {
                closeOpenTaskFlow();
              }
              const summary = data.results?.find((r: any) => r.action === 'summarize' || r.type === 'summary');
              if (summary?.output && window.electron) window.electron.showSummary(summary.output);
            } else if (data.type === 'error') {
              if (!isOpen) {
                setHistory(prev => [...prev, { role: 'assistant', content: `Error: ${data.content}` }]);
              }
              setIsProcessing(false);
              if (isOpen) {
                closeOpenTaskFlow();
              }
            } else if (data.type === 'stopped') {
              setIsProcessing(false);
              if (isOpen) {
                closeOpenTaskFlow();
              }
            }
          } catch (e) { }
        }
      }
    } catch (error) {
      console.error("Submit error:", error);
      setIsProcessing(false);
      if (isOpen) {
        closeOpenTaskFlow();
      } else {
        setHistory(prev => [...prev, { role: 'assistant', content: "Connection error. Is backend running?" }]);
      }
    }
  }, [history, closeOpenTaskFlow]);

  useEffect(() => {
    const eventSource = new EventSource(`${BACKEND_URL}/screenshot/events`);
    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'screenshot') {
          setIsGlowActive(true);
          setTimeout(() => setIsGlowActive(false), 1500);
        }
      } catch (e) {
        console.error("SSE parse error:", e);
      }
    };
    return () => eventSource.close();
  }, []);

  useEffect(() => {
    if (window.electron) {
      window.electron.onWindowShow((data) => {
        if (hideTimeoutRef.current) {
          clearTimeout(hideTimeoutRef.current);
          hideTimeoutRef.current = null;
        }
        setIsVisible(true);
        setAnimationPhase('expanded');
        fetch(`${BACKEND_URL}/visibility`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ visible: true }) });
        if (data?.activeApp) { setActiveApp(data.activeApp); fetchActiveApp(); }
      });
      window.electron.onWindowHide(() => {
        fetch(`${BACKEND_URL}/visibility`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ visible: false }) });
        if (window.electron?.showAutomationOverlay) {
          window.electron.showAutomationOverlay(false).catch(() => {});
        }
        setIsVisible(false);
        setAnimationPhase('hidden');
      });
      }
      return () => {
      if (hideTimeoutRef.current) {
        clearTimeout(hideTimeoutRef.current);
        hideTimeoutRef.current = null;
      }
    };
  }, [fetchActiveApp]);

  useEffect(() => {
    if (!isVisible || isProcessing) return;
    fetchActiveApp();
    const interval = setInterval(fetchActiveApp, 2000);
    return () => clearInterval(interval);
  }, [isVisible, isProcessing, fetchActiveApp]);

  useEffect(() => {
    if (!window.electron) return;
    let height = 220;
    if (showPresets) height = 500;
    else if (showSettings) height = 560;
    else if (openTaskFlowActive) height = 250;
    else if (history.length > 0) height = Math.min(560, 260 + history.length * 50);
    window.electron.resizeWindow(370, height);
  }, [showPresets, showSettings, history.length, openTaskFlowActive]);

  useEffect(() => {
    if (window.electron?.showAutomationOverlay) {
      const showOpenTaskOverlay = openTaskFlowActive && openTaskPillVisible;
      window.electron.showAutomationOverlay(showOpenTaskOverlay);
    }
  }, [openTaskFlowActive, openTaskPillVisible]);

  useEffect(() => {
    return () => {
      if (window.electron?.showAutomationOverlay) {
        window.electron.showAutomationOverlay(false).catch(() => {});
      }
      if (openTaskCloseTimerRef.current) {
        clearTimeout(openTaskCloseTimerRef.current);
        openTaskCloseTimerRef.current = null;
      }
    };
  }, []);


  if (isSummaryMode) return <SummaryView />;
  if (isOverlayMode) return null;

  return (
    <div className="relative flex h-screen w-screen items-end justify-center bg-transparent overflow-hidden pb-10 px-4">
      <AnimatePresence>
        {openTaskFlowActive && openTaskPillVisible && (
          <motion.div
            key="open-task-pill"
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
            className="absolute bottom-[112px] z-[70] px-3.5 py-2 rounded-full border border-white/20 bg-black/95 text-white text-[12px] font-medium shadow-[0_8px_24px_-12px_rgba(0,0,0,0.9)]"
          >
            {openTaskLabel || "Working..."}
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence mode="popLayout" initial={false}>
        {showSettings && (
            <motion.div
              key="settings"
              initial={{ opacity: 0, y: 10, scale: 0.985, filter: "blur(8px)" }}
              animate={{ opacity: 1, y: 0, scale: 1, filter: "blur(0px)" }}
              exit={{ opacity: 0, y: 8, scale: 0.98, filter: "blur(8px)" }}
              transition={{
                duration: 0.36,
                ease: [0.22, 1, 0.36, 1],
                opacity: { duration: 0.3, ease: [0.33, 1, 0.68, 1] },
                y: { duration: 0.32, ease: [0.22, 1, 0.36, 1] }
              }}
              className="absolute bottom-[118px] z-[60] w-full max-w-[340px] h-[450px]"
          >
            <SettingsManager onClose={() => setShowSettings(false)} onResetHistory={handleReset} />
          </motion.div>
        )}
      </AnimatePresence>

      <LayoutGroup>
        <ApiKeyModal isOpen={authNeeded} onSuccess={() => setAuthNeeded(false)} />
        <AnimatePresence mode="wait">
          {isVisible && (
            <motion.div
              key="main"
              variants={containerVariants}
              initial="hidden"
              animate={isWiping ? { opacity: 0, filter: "blur(10px)" } : "visible"}
              exit="exit"
              className="w-full flex flex-col items-center"
            >
              <div className="relative flex flex-col items-center gap-1 w-full max-w-[370px]">
                <motion.div
                  layout
                  layoutId="prism-container"
                  animate={{
                    width: animationPhase === 'expanded' ? 350 : 52,
                    height: animationPhase === 'expanded' ? (showPresets ? 500 : "auto") : 52,
                    borderRadius: animationPhase === 'expanded' ? 32 : 28,
                    opacity: showSettings ? 0.8 : 1,
                    filter: showSettings ? "blur(1.5px)" : "blur(0px)",
                    scale: showSettings ? 0.975 : 1,
                    y: showSettings ? 6 : 0,
                  }}
                  transition={{
                    ...springConfig,
                    opacity: { duration: 0.22, ease: [0.22, 1, 0.36, 1] },
                    filter: { duration: 0.24, ease: [0.22, 1, 0.36, 1] },
                    scale: { duration: 0.24, ease: [0.22, 1, 0.36, 1] },
                    y: { duration: 0.24, ease: [0.22, 1, 0.36, 1] },
                    layout: {
                      duration: animationPhase === 'collapsing' ? 0.22 : 0.34,
                      ease: [0.23, 1, 0.32, 1]
                    }
                  }}
                  className={cn(
                    "relative z-50 transition-colors duration-150",
                    showPresets || showSettings
                      ? "overflow-hidden bg-black/95 backdrop-blur-3xl border shadow-[0_10px_40px_-15px_rgba(0,0,0,0.5),0_0_20px_rgba(255,255,255,0.05)]"
                      : "overflow-visible bg-transparent border-transparent shadow-none",
                    animationPhase === "collapsing" ? "border-transparent" : (showPresets || showSettings ? "border-white/15" : "border-transparent")
                  )}
                  onClick={() => {
                    if (animationPhase !== 'expanded') {
                      setAnimationPhase('expanded');
                      setShowSettings(true);
                    }
                  }}
                >
                  <AnimatePresence mode="popLayout" initial={false}>
                    {animationPhase === 'expanded' ? (
                      <motion.div
                        key="exp"
                        initial={{ opacity: 0, filter: "blur(4px)" }}
                        animate={{ opacity: 1, filter: "blur(0px)" }}
                        exit={{ opacity: 0, filter: "blur(4px)" }}
                        transition={{ duration: 0.2 }}
                      >
                        <AnimatePresence mode="wait">
                          {showPresets ? (
                            <PresetManager key="pre" onClose={() => setShowPresets(false)} onRun={handleRunPreset} isProcessing={isProcessing} />
                          ) : (
                            <motion.div
                              key="in"
                              initial={{ opacity: 0, y: 10 }}
                              animate={{ opacity: 1, y: 0 }}
                              exit={{ opacity: 0, y: -10 }}
                              transition={springConfig}
                            >
                              <AIInputWithFile
                                key={resetKey}
                                onSubmit={handleSubmit}
                                onClearReply={() => { setHistory([]); setResetKey(k => k + 1); }}
                                onShowPresets={() => setShowPresets(true)}
                                onDoubleClickLogo={() => setShowSettings(true)}
                                placeholder="How can I help?"
                                isProcessing={isProcessing}
                                history={openTaskFlowActive ? [] : history}
                                activeApp={activeApp}
                                isGlowActive={isGlowActive}
                              />
                            </motion.div>
                          )}
                        </AnimatePresence>
                      </motion.div>
                    ) : (
                      <motion.div
                        key="logo"
                        className="w-14 h-14 flex items-center justify-center hover:bg-white/5 transition-colors cursor-pointer"
                      >
                        <motion.div
                          layoutId="logo"
                          animate={isGlowActive ? {
                            filter: [
                              "drop-shadow(0 0 0px rgba(255,255,255,0))",
                              "drop-shadow(0 0 12px rgba(255,255,255,0.8))",
                              "drop-shadow(0 0 0px rgba(255,255,255,0))"
                            ]
                          } : {
                            filter: "drop-shadow(0 0 0px rgba(255,255,255,0))"
                          }}
                          transition={{ duration: 1.5, ease: "easeInOut" }}
                        >
                          <PrismIcon className="w-7 h-7" />
                        </motion.div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </motion.div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </LayoutGroup>
    </div>
  );
}
