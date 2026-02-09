"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.default = App;
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = require("react");
const AIInputWithFile_1 = require("./components/ui/AIInputWithFile");
const utils_1 = require("./lib/utils");
const framer_motion_1 = require("framer-motion");
const SummaryView_1 = __importDefault(require("./components/SummaryView"));
const PresetManager_1 = __importDefault(require("./components/PresetManager"));
const SettingsManager_1 = __importDefault(require("./components/SettingsManager"));
const PrismIcon_1 = require("./components/ui/PrismIcon");
const ApiKeyModal_1 = __importDefault(require("./components/ApiKeyModal"));
const BACKEND_URL = "http://localhost:8000";
const isOpenCommand = (message) => /^\s*open\b/i.test(message);
const isBankOpenCommand = (message) => {
    if (!isOpenCommand(message))
        return false;
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
function App() {
    const queryParams = new URLSearchParams(window.location.search);
    const isSummaryMode = queryParams.get('mode') === 'summary';
    const isOverlayMode = queryParams.get('mode') === 'overlay';
    const [isVisible, setIsVisible] = (0, react_1.useState)(true);
    const [animationPhase, setAnimationPhase] = (0, react_1.useState)('expanded');
    const [isProcessing, setIsProcessing] = (0, react_1.useState)(false);
    const [history, setHistory] = (0, react_1.useState)([]);
    const [resetKey, setResetKey] = (0, react_1.useState)(0);
    const [isWiping, setIsWiping] = (0, react_1.useState)(false);
    const [activeApp, setActiveApp] = (0, react_1.useState)("Desktop");
    const [showPresets, setShowPresets] = (0, react_1.useState)(false);
    const [showSettings, setShowSettings] = (0, react_1.useState)(false);
    const [authNeeded, setAuthNeeded] = (0, react_1.useState)(false);
    const [isGlowActive, setIsGlowActive] = (0, react_1.useState)(false);
    const [openTaskFlowActive, setOpenTaskFlowActive] = (0, react_1.useState)(false);
    const [openTaskPillVisible, setOpenTaskPillVisible] = (0, react_1.useState)(false);
    const [openTaskLabel, setOpenTaskLabel] = (0, react_1.useState)("");
    const openTaskStartedAtRef = (0, react_1.useRef)(0);
    const openTaskCloseTimerRef = (0, react_1.useRef)(null);
    const lastSpacePress = (0, react_1.useRef)(0);
    const spacePressCount = (0, react_1.useRef)(0);
    const hideTimeoutRef = (0, react_1.useRef)(null);
    const springConfig = { type: "spring", damping: 25, stiffness: 350, mass: 1 };
    const containerVariants = {
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
    const checkAuth = (0, react_1.useCallback)(async () => {
        try {
            const res = await fetch(`${BACKEND_URL}/check-auth`);
            const data = await res.json();
            if (data.authenticated === false) {
                setAuthNeeded(true);
            }
            else {
                setAuthNeeded(false);
            }
        }
        catch (e) {
            console.error("Auth check failed:", e);
        }
    }, []);
    (0, react_1.useEffect)(() => {
        checkAuth();
    }, [checkAuth]);
    const fetchActiveApp = (0, react_1.useCallback)(async () => {
        try {
            const response = await fetch(`${BACKEND_URL}/active-app`);
            if (!response.ok)
                return;
            const data = await response.json();
            if (data.success && data.app_name !== activeApp) {
                setActiveApp(data.app_name);
            }
        }
        catch (e) {
            console.error("App fetch failed:", e);
        }
    }, [activeApp]);
    const handleReset = (0, react_1.useCallback)(async () => {
        setIsWiping(true);
        await new Promise(r => setTimeout(r, 300));
        try {
            await fetch(`${BACKEND_URL}/reset`, { method: 'POST' });
        }
        catch (e) {
            console.error("Reset failed:", e);
        }
        finally {
            setHistory([]);
            setIsProcessing(false);
            setOpenTaskFlowActive(false);
            setOpenTaskPillVisible(false);
            setOpenTaskLabel("");
            if (window.electron?.showAutomationOverlay) {
                window.electron.showAutomationOverlay(false).catch(() => { });
            }
            if (openTaskCloseTimerRef.current) {
                clearTimeout(openTaskCloseTimerRef.current);
                openTaskCloseTimerRef.current = null;
            }
            setResetKey(prev => prev + 1);
            if (window.electron)
                window.electron.resizeWindow(370, 220);
            setIsWiping(false);
        }
    }, []);
    const handleKill = (0, react_1.useCallback)(async () => {
        try {
            await fetch(`${BACKEND_URL}/reset`, { method: 'POST' });
            if (window.electron)
                await window.electron.hideWindow();
            setIsProcessing(false);
            setHistory([]);
            setOpenTaskFlowActive(false);
            setOpenTaskPillVisible(false);
            setOpenTaskLabel("");
            if (window.electron?.showAutomationOverlay) {
                window.electron.showAutomationOverlay(false).catch(() => { });
            }
            if (openTaskCloseTimerRef.current) {
                clearTimeout(openTaskCloseTimerRef.current);
                openTaskCloseTimerRef.current = null;
            }
            setResetKey(prev => prev + 1);
        }
        catch (e) {
            console.error("Kill failed:", e);
        }
    }, []);
    const closeOpenTaskFlow = (0, react_1.useCallback)(() => {
        const MIN_PILL_VISIBLE_MS = 700;
        const elapsed = Date.now() - openTaskStartedAtRef.current;
        const wait = Math.max(0, MIN_PILL_VISIBLE_MS - elapsed);
        if (openTaskCloseTimerRef.current) {
            clearTimeout(openTaskCloseTimerRef.current);
        }
        openTaskCloseTimerRef.current = setTimeout(() => {
            setOpenTaskPillVisible(false);
            if (window.electron?.showAutomationOverlay) {
                window.electron.showAutomationOverlay(false).catch(() => { });
            }
            setTimeout(() => setOpenTaskFlowActive(false), 260);
            openTaskCloseTimerRef.current = null;
        }, wait);
    }, []);
    const handleRunPreset = (0, react_1.useCallback)(async (preset) => {
        setIsProcessing(true);
        setShowPresets(false);
        const newHistory = [...history, { role: 'user', content: `Workflow: ${preset.name}` }];
        setHistory(newHistory);
        try {
            if (window.electron) {
                const result = await window.electron.executePreset(preset.steps, newHistory);
                setIsProcessing(false);
                if (result.reply)
                    setHistory(prev => [...prev, { role: 'assistant', content: result.reply }]);
            }
        }
        catch (error) {
            console.error("Preset error:", error);
            setIsProcessing(false);
        }
    }, [history]);
    (0, react_1.useEffect)(() => {
        const handleKeyDown = (e) => {
            if (e.altKey && e.code === 'KeyC') {
                e.preventDefault();
                handleReset();
            }
            if (e.altKey && e.code === 'Space') {
                const now = Date.now();
                if (now - lastSpacePress.current < 500)
                    spacePressCount.current += 1;
                else
                    spacePressCount.current = 1;
                lastSpacePress.current = now;
                if (spacePressCount.current === 2) {
                    handleReset();
                    spacePressCount.current = 0;
                    return;
                }
                if (isProcessing)
                    handleKill();
            }
        };
        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [isProcessing, handleKill, handleReset]);
    const handleSubmit = (0, react_1.useCallback)(async (message, file) => {
        const isOpen = isOpenCommand(message);
        const isBankOpen = isBankOpenCommand(message);
        if (isOpen && isBankOpen) {
            setIsProcessing(false);
            setOpenTaskFlowActive(true);
            setOpenTaskLabel("Can't open bank or banking websites.");
            setOpenTaskPillVisible(true);
            if (window.electron?.showAutomationOverlay) {
                window.electron.showAutomationOverlay(false).catch(() => { });
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
                window.electron.showAutomationOverlay(true).catch(() => { });
            }
        }
        else {
            setOpenTaskPillVisible(false);
            setOpenTaskLabel("");
            if (window.electron?.showAutomationOverlay) {
                window.electron.showAutomationOverlay(false).catch(() => { });
            }
        }
        const currentHistory = isOpen
            ? [...history]
            : [...history, { role: 'user', content: message }];
        if (!isOpen) {
            setHistory(currentHistory);
        }
        try {
            const formData = new FormData();
            formData.append('command', message);
            formData.append('history', JSON.stringify(currentHistory));
            if (file)
                formData.append('file', file);
            const response = await fetch(`${BACKEND_URL}/execute-stream`, { method: 'POST', body: formData });
            if (!response.body)
                throw new Error("No body");
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let assistantReply = "";
            while (true) {
                const { done, value } = await reader.read();
                if (done)
                    break;
                const chunk = decoder.decode(value, { stream: true });
                const lines = chunk.split('\n');
                for (const line of lines) {
                    if (!line.startsWith('data: '))
                        continue;
                    try {
                        const dataStr = line.slice(6).trim();
                        if (!dataStr)
                            continue;
                        const data = JSON.parse(dataStr);
                        if (data.type === 'reply_start') {
                            if (!isOpen) {
                                setHistory(prev => [...prev, { role: 'assistant', content: "" }]);
                            }
                        }
                        else if (data.type === 'tasks') {
                            if (isOpen) {
                                const tasks = Array.isArray(data.tasks) ? data.tasks : [];
                                const activeTask = tasks.find((t) => t.status === "in_progress") || tasks.find((t) => t.status === "pending");
                                if (activeTask?.label) {
                                    setOpenTaskLabel(String(activeTask.label));
                                    setOpenTaskPillVisible(true);
                                }
                            }
                        }
                        else if (data.type === 'reply_chunk') {
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
                        }
                        else if (data.type === 'done') {
                            setIsProcessing(false);
                            if (isOpen) {
                                closeOpenTaskFlow();
                            }
                            const summary = data.results?.find((r) => r.action === 'summarize' || r.type === 'summary');
                            if (summary?.output && window.electron)
                                window.electron.showSummary(summary.output);
                        }
                        else if (data.type === 'error') {
                            if (!isOpen) {
                                setHistory(prev => [...prev, { role: 'assistant', content: `Error: ${data.content}` }]);
                            }
                            setIsProcessing(false);
                            if (isOpen) {
                                closeOpenTaskFlow();
                            }
                        }
                        else if (data.type === 'stopped') {
                            setIsProcessing(false);
                            if (isOpen) {
                                closeOpenTaskFlow();
                            }
                        }
                    }
                    catch (e) { }
                }
            }
        }
        catch (error) {
            console.error("Submit error:", error);
            setIsProcessing(false);
            if (isOpen) {
                closeOpenTaskFlow();
            }
            else {
                setHistory(prev => [...prev, { role: 'assistant', content: "Connection error. Is backend running?" }]);
            }
        }
    }, [history, closeOpenTaskFlow]);
    (0, react_1.useEffect)(() => {
        const eventSource = new EventSource(`${BACKEND_URL}/screenshot/events`);
        eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data.type === 'screenshot') {
                    setIsGlowActive(true);
                    setTimeout(() => setIsGlowActive(false), 1500);
                }
            }
            catch (e) {
                console.error("SSE parse error:", e);
            }
        };
        return () => eventSource.close();
    }, []);
    (0, react_1.useEffect)(() => {
        if (window.electron) {
            window.electron.onWindowShow((data) => {
                if (hideTimeoutRef.current) {
                    clearTimeout(hideTimeoutRef.current);
                    hideTimeoutRef.current = null;
                }
                setIsVisible(true);
                setAnimationPhase('expanded');
                fetch(`${BACKEND_URL}/visibility`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ visible: true }) });
                if (data?.activeApp) {
                    setActiveApp(data.activeApp);
                    fetchActiveApp();
                }
            });
            window.electron.onWindowHide(() => {
                fetch(`${BACKEND_URL}/visibility`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ visible: false }) });
                if (window.electron?.showAutomationOverlay) {
                    window.electron.showAutomationOverlay(false).catch(() => { });
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
    (0, react_1.useEffect)(() => {
        if (!isVisible || isProcessing)
            return;
        fetchActiveApp();
        const interval = setInterval(fetchActiveApp, 2000);
        return () => clearInterval(interval);
    }, [isVisible, isProcessing, fetchActiveApp]);
    (0, react_1.useEffect)(() => {
        if (!window.electron)
            return;
        let height = 220;
        if (showPresets)
            height = 500;
        else if (showSettings)
            height = 560;
        else if (openTaskFlowActive)
            height = 250;
        else if (history.length > 0)
            height = Math.min(560, 260 + history.length * 50);
        window.electron.resizeWindow(370, height);
    }, [showPresets, showSettings, history.length, openTaskFlowActive]);
    (0, react_1.useEffect)(() => {
        if (window.electron?.showAutomationOverlay) {
            const showOpenTaskOverlay = openTaskFlowActive && openTaskPillVisible;
            window.electron.showAutomationOverlay(showOpenTaskOverlay);
        }
    }, [openTaskFlowActive, openTaskPillVisible]);
    (0, react_1.useEffect)(() => {
        return () => {
            if (window.electron?.showAutomationOverlay) {
                window.electron.showAutomationOverlay(false).catch(() => { });
            }
            if (openTaskCloseTimerRef.current) {
                clearTimeout(openTaskCloseTimerRef.current);
                openTaskCloseTimerRef.current = null;
            }
        };
    }, []);
    if (isSummaryMode)
        return (0, jsx_runtime_1.jsx)(SummaryView_1.default, {});
    if (isOverlayMode)
        return null;
    return ((0, jsx_runtime_1.jsxs)("div", { className: "relative flex h-screen w-screen items-end justify-center bg-transparent overflow-hidden pb-10 px-4", children: [(0, jsx_runtime_1.jsx)(framer_motion_1.AnimatePresence, { children: openTaskFlowActive && openTaskPillVisible && ((0, jsx_runtime_1.jsx)(framer_motion_1.motion.div, { initial: { opacity: 0, y: 6 }, animate: { opacity: 1, y: 0 }, exit: { opacity: 0, y: -4 }, transition: { duration: 0.22, ease: [0.22, 1, 0.36, 1] }, className: "absolute bottom-[112px] z-[70] px-3.5 py-2 rounded-full border border-white/20 bg-black/95 text-white text-[12px] font-medium shadow-[0_8px_24px_-12px_rgba(0,0,0,0.9)]", children: openTaskLabel || "Working..." }, "open-task-pill")) }), (0, jsx_runtime_1.jsx)(framer_motion_1.AnimatePresence, { mode: "popLayout", initial: false, children: showSettings && ((0, jsx_runtime_1.jsx)(framer_motion_1.motion.div, { initial: { opacity: 0, filter: "blur(10px)", scale: 0.985 }, animate: { opacity: 1, filter: "blur(0px)", scale: 1 }, exit: { opacity: 0, filter: "blur(10px)", scale: 0.985 }, transition: {
                        duration: 0.34,
                        ease: [0.22, 1, 0.36, 1],
                        opacity: { duration: 0.28, ease: [0.33, 1, 0.68, 1] }
                    }, className: "absolute bottom-[118px] z-[60] w-full max-w-[340px] h-[450px]", children: (0, jsx_runtime_1.jsx)(SettingsManager_1.default, { onClose: () => setShowSettings(false), onResetHistory: handleReset }) }, "settings")) }), (0, jsx_runtime_1.jsxs)(framer_motion_1.LayoutGroup, { children: [(0, jsx_runtime_1.jsx)(ApiKeyModal_1.default, { isOpen: authNeeded, onSuccess: () => setAuthNeeded(false) }), (0, jsx_runtime_1.jsx)(framer_motion_1.AnimatePresence, { mode: "wait", children: isVisible && ((0, jsx_runtime_1.jsx)(framer_motion_1.motion.div, { variants: containerVariants, initial: "hidden", animate: isWiping ? { opacity: 0, filter: "blur(10px)" } : "visible", exit: "exit", className: "w-full flex flex-col items-center", children: (0, jsx_runtime_1.jsx)("div", { className: "relative flex flex-col items-center gap-1 w-full max-w-[370px]", children: (0, jsx_runtime_1.jsx)(framer_motion_1.motion.div, { layout: true, layoutId: "prism-container", animate: {
                                        width: animationPhase === 'expanded' ? 350 : 52,
                                        height: animationPhase === 'expanded' ? (showPresets ? 500 : "auto") : 52,
                                        borderRadius: animationPhase === 'expanded' ? 32 : 28,
                                        opacity: showSettings ? 0.8 : 1,
                                        filter: showSettings ? "blur(1.5px)" : "blur(0px)",
                                        scale: showSettings ? 0.975 : 1,
                                        y: showSettings ? 6 : 0,
                                    }, transition: {
                                        ...springConfig,
                                        opacity: { duration: 0.22, ease: [0.22, 1, 0.36, 1] },
                                        filter: { duration: 0.24, ease: [0.22, 1, 0.36, 1] },
                                        scale: { duration: 0.24, ease: [0.22, 1, 0.36, 1] },
                                        y: { duration: 0.24, ease: [0.22, 1, 0.36, 1] },
                                        layout: {
                                            duration: animationPhase === 'collapsing' ? 0.22 : 0.34,
                                            ease: [0.23, 1, 0.32, 1]
                                        }
                                    }, className: (0, utils_1.cn)("relative z-50 transition-colors duration-150", showPresets || showSettings
                                        ? "overflow-hidden bg-black/95 backdrop-blur-3xl border shadow-[0_10px_40px_-15px_rgba(0,0,0,0.5),0_0_20px_rgba(255,255,255,0.05)]"
                                        : "overflow-visible bg-transparent border-transparent shadow-none", animationPhase === "collapsing" ? "border-transparent" : (showPresets || showSettings ? "border-white/15" : "border-transparent")), onClick: () => {
                                        if (animationPhase !== 'expanded') {
                                            setAnimationPhase('expanded');
                                            setShowSettings(true);
                                        }
                                    }, children: (0, jsx_runtime_1.jsx)(framer_motion_1.AnimatePresence, { mode: "popLayout", initial: false, children: animationPhase === 'expanded' ? ((0, jsx_runtime_1.jsx)(framer_motion_1.motion.div, { initial: { opacity: 0, filter: "blur(4px)" }, animate: { opacity: 1, filter: "blur(0px)" }, exit: { opacity: 0, filter: "blur(4px)" }, transition: { duration: 0.2 }, children: (0, jsx_runtime_1.jsx)(framer_motion_1.AnimatePresence, { mode: "wait", children: showPresets ? ((0, jsx_runtime_1.jsx)(PresetManager_1.default, { onClose: () => setShowPresets(false), onRun: handleRunPreset, isProcessing: isProcessing }, "pre")) : ((0, jsx_runtime_1.jsx)(framer_motion_1.motion.div, { initial: { opacity: 0, y: 10 }, animate: { opacity: 1, y: 0 }, exit: { opacity: 0, y: -10 }, transition: springConfig, children: (0, jsx_runtime_1.jsx)(AIInputWithFile_1.AIInputWithFile, { onSubmit: handleSubmit, onClearReply: () => { setHistory([]); setResetKey(k => k + 1); }, onShowPresets: () => setShowPresets(true), onDoubleClickLogo: () => setShowSettings(true), placeholder: "How can I help?", isProcessing: isProcessing, history: openTaskFlowActive ? [] : history, activeApp: activeApp, isGlowActive: isGlowActive }, resetKey) }, "in")) }) }, "exp")) : ((0, jsx_runtime_1.jsx)(framer_motion_1.motion.div, { className: "w-14 h-14 flex items-center justify-center hover:bg-white/5 transition-colors cursor-pointer", children: (0, jsx_runtime_1.jsx)(framer_motion_1.motion.div, { layoutId: "logo", animate: isGlowActive ? {
                                                    filter: [
                                                        "drop-shadow(0 0 0px rgba(255,255,255,0))",
                                                        "drop-shadow(0 0 12px rgba(255,255,255,0.8))",
                                                        "drop-shadow(0 0 0px rgba(255,255,255,0))"
                                                    ]
                                                } : {
                                                    filter: "drop-shadow(0 0 0px rgba(255,255,255,0))"
                                                }, transition: { duration: 1.5, ease: "easeInOut" }, children: (0, jsx_runtime_1.jsx)(PrismIcon_1.PrismIcon, { className: "w-7 h-7" }) }) }, "logo")) }) }) }) }, "main")) })] })] }));
}
