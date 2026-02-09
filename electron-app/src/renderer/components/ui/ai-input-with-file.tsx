"use client";

import { CornerRightUp, FileUp, Paperclip, X, Plus, Info, Image as ImageIcon, FileText } from "lucide-react";
import { PrismIcon } from "./prism-icon";
import { useState, useRef, useEffect, useCallback } from "react";
import { cn } from "@/lib/utils";
import { useFileInput } from "@/hooks/use-file-input";
import { useAutoResizeTextarea } from "@/hooks/use-auto-resize-textarea";
import { Textarea } from "@/components/ui/textarea";
import { motion, AnimatePresence, LayoutGroup } from "framer-motion";
import { WeatherTime, VisualMemoryCircle } from "../ChatBarWidgets";

interface FileDisplayProps {
  fileName: string;
  onClear: () => void;
}

function FileDisplay({ fileName, onClear }: FileDisplayProps) {
  return (
    <div className="flex items-center gap-2 bg-black px-3 py-1.5 rounded-full border border-white/10 w-fit group">
      <FileUp className="w-3.5 h-3.5 text-white/50" />
      <span className="text-[12px] font-medium text-white/80 max-w-[150px] truncate">
        {fileName}
      </span>
      <button 
        onClick={onClear}
        className="ml-1 p-0.5 rounded-full hover:bg-white/10 transition-colors"
      >
        <X className="w-3 h-3 text-white/40" />
      </button>
    </div>
  );
}

interface AIInputWithFileProps {
  id?: string;
  placeholder?: string;
  minHeight?: number;
  maxHeight?: number;
  accept?: string;
  maxFileSize?: number;
  onSubmit?: (message: string, file?: File) => void;
  onSizeChange?: (isSmall: boolean) => void;
  onClearReply?: () => void;
    onShowPresets?: () => void;
    onDoubleClickLogo?: () => void;
    onToggleWidgets?: () => void;
    className?: string;
    isProcessing?: boolean;
    history?: { role: 'user' | 'assistant', content: string }[];
    activeApp?: string;
    isCoding?: boolean;
    shortcuts?: string[];
      allowTopWidgets?: boolean;
      logoLayoutId?: string;
      isGlowActive?: boolean;
    }
    
function DocumentPill({ fileName, onClear }: { fileName: string, onClear: () => void }) {
    const isImage = /\.(jpg|jpeg|png|webp|gif)$/i.test(fileName);
    const isPDF = /\.pdf$/i.test(fileName);

  return (
    <motion.button
      initial={{ opacity: 0, scale: 0.9, y: 10 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.9, y: 10 }}
      whileHover={{ scale: 1.02 }}
        whileTap={{ scale: 0.98 }}
        onClick={onClear}
          className="flex items-center gap-2.5 px-4 py-2.5 rounded-full border border-white/20 bg-black/95 backdrop-blur-sm transition-all w-fit group shadow-[0_8px_24px_-16px_rgba(0,0,0,0.75)]"
      >
        <div className="p-1.5 rounded-full bg-transparent transition-colors">
        {isImage ? (
          <ImageIcon className="w-5 h-5 text-emerald-400" />
        ) : isPDF ? (
          <FileText className="w-5 h-5 text-red-400" />
        ) : (
          <FileUp className="w-5 h-5 text-blue-400" />
        )}
      </div>
      
      <div className="flex flex-col items-start gap-0.5">
        <span className="text-[13px] font-bold text-white leading-none">
          {isImage ? "Attached Image" : isPDF ? "Attached PDF" : "Attached Document"}
        </span>
        <span className="text-[11px] font-medium text-white/50 leading-none truncate max-w-[180px]">
          {fileName}
        </span>
      </div>

      <div className="ml-1 p-1 rounded-full opacity-0 group-hover:opacity-100 transition-all">
        <X className="w-3.5 h-3.5 text-white/40" />
      </div>
    </motion.button>
  );
}

export function AIInputWithFile({
    id = "ai-input-with-file",
    placeholder = "Type a message or upload a file...",
    minHeight = 24,
    maxHeight = 400,
    accept = "application/pdf,.pdf,.doc,.docx,.txt,text/plain,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document,image/*",
    maxFileSize = 10,
    onSubmit,
    onSizeChange,
    onClearReply,
    onShowPresets,
    onDoubleClickLogo,
    className,
    isProcessing = false,
    history = [],
    activeApp = "Desktop",
    isCoding = false,
    shortcuts = [],
    allowTopWidgets = false,
    onToggleWidgets,
    logoLayoutId,
    isGlowActive = false,
  }: AIInputWithFileProps) {

  const [memoryStatus, setMemoryStatus] = useState<{

    is_recording: boolean;
    frame_count: number;
    duration_minutes: number;
    max_minutes: number;
  } | null>(null);

  const [presets, setPresets] = useState<any[]>([]);
  const [tokenCount, setTokenCount] = useState<number>(0);
  const [inputValue, setInputValue] = useState<string>("");
  const [isDragOver, setIsDragOver] = useState(false);
  const shouldClearAttachmentAfterTaskRef = useRef(false);
  const prevProcessingRef = useRef(isProcessing);
    const [isFocused, setIsFocused] = useState(false);
    const [showWidgets, setShowWidgets] = useState(false);

  const { fileName, error, fileInputRef, handleFileSelect, clearFile, selectedFile, validateAndSetFile } =
    useFileInput({ accept, maxSize: maxFileSize });

  const { textareaRef, adjustHeight, height } = useAutoResizeTextarea({
    minHeight,
    maxHeight,
  });

    const handleSubmit = () => {
      if (inputValue.trim() || selectedFile) {
        if (selectedFile) {
          shouldClearAttachmentAfterTaskRef.current = true;
        }
        onSubmit?.(inputValue, selectedFile);
        
        // Increment token count realistically
        const tokens = inputValue.length * 4 + (selectedFile ? 50000 : 0);
        setTokenCount(prev => Math.min(prev + tokens, 1000000));
        
        setInputValue("");
        adjustHeight(true);
      }
    };

  const handleClearAttachment = useCallback(() => {
    shouldClearAttachmentAfterTaskRef.current = false;
    clearFile();
  }, [clearFile]);

    const renderMessageContent = (content: string) => {
        return content;
      };


  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await fetch("http://localhost:8000/memory-status");
        if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
        const text = await res.text();
        if (text) {
          const data = JSON.parse(text);
          setMemoryStatus(data);
        }
      } catch (e) {
        console.error("Failed to fetch memory status:", e);
      }

      try {
        const res = await fetch("http://localhost:8000/tokens");
        if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
        const text = await res.text();
        if (text) {
          const data = JSON.parse(text);
          if (data.success) {
            setTokenCount(data.total_tokens);
          }
        }
      } catch (e) {
        console.error("Failed to fetch token count:", e);
      }

      if (window.electron) {
        const p = await window.electron.getPresets();
        setPresets(p || []);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, []);

  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  }, []);

  const onDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  }, []);

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) {
      validateAndSetFile(file);
    }
  }, [validateAndSetFile]);

  useEffect(() => {
    if (prevProcessingRef.current && !isProcessing && shouldClearAttachmentAfterTaskRef.current) {
      clearFile();
      shouldClearAttachmentAfterTaskRef.current = false;
    }
    prevProcessingRef.current = isProcessing;
  }, [isProcessing, clearFile]);

  return (
    <div 
      className={cn(
        "w-full flex flex-col items-center gap-3 transition-all",
        isDragOver && "rounded-2xl ring-1 ring-white/25 bg-white/[0.02]",
        className
      )}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
    >
        {/* Top Row Widgets */}
        <AnimatePresence>
          {allowTopWidgets && showWidgets && (
            <motion.div 
              initial={{ opacity: 0, y: 5, filter: "blur(4px)" }}
              animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
                exit={{ opacity: 0, y: 5, filter: "blur(4px)" }}
                transition={{ type: "spring", damping: 25, stiffness: 350 }}
                className="flex justify-between items-end w-full px-1 max-w-[440px]"

            >
              <div className="flex gap-2 items-center">
                {/* Presets (P1, P2) */}
                <div className="flex gap-2">
                {presets.length > 0 ? (
                  presets.slice(0, 2).map((p, i) => (
                      <button
                        key={p.id}
                        onClick={() => onShowPresets?.()}
                          className="px-4 py-1.5 bg-black rounded-full border border-white/10 text-[11px] font-bold text-white/70 hover:text-white hover:bg-zinc-900 transition-all"
                      >
                        P{i + 1}
                      </button>
                    ))
                  ) : (
                    <button
                      onClick={() => onShowPresets?.()}
                        className="px-4 py-1.5 bg-black rounded-full border border-white/10 text-[11px] font-bold text-white/70 hover:text-white hover:bg-zinc-900 transition-all flex items-center gap-1.5"
                    >
                    <Plus className="w-3 h-3" />
                    Create Preset
                  </button>
                )}
              </div>
            </div>

            {/* Weather & Time */}
            <WeatherTime />
          </motion.div>
        )}
        </AnimatePresence>

        <AnimatePresence>
          {fileName && (
            <div className="w-full max-w-[440px] flex justify-center mb-2 px-1">
              <DocumentPill fileName={fileName} onClear={handleClearAttachment} />
            </div>
          )}
        </AnimatePresence>

        <AnimatePresence>
          {error && (
            <motion.div
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 6 }}
              className="w-full max-w-[440px] text-[11px] text-red-300/90 px-1"
            >
              {error}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Main Chat Bar */}
        <div
          className={cn(
            "relative w-full flex flex-col",
            history.length > 0 && "bg-black/95 backdrop-blur-xl border border-white/10 rounded-[26px] shadow-2xl overflow-visible"
          )}
        >
        {/* History / File Preview Area */}
        <AnimatePresence mode="popLayout">
          {history.length > 0 && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="flex flex-col border-b border-white/5"
            >
              {/* History Messages */}
              {history.length > 0 && (
                <div
                  className="px-4 py-4 flex flex-col gap-4 max-h-[300px] overflow-y-auto [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden"
                  style={{ scrollbarWidth: "none", msOverflowStyle: "none" }}
                >
                  {history.map((msg, i) => (
                      <motion.div
                        key={i}
                        initial={{ opacity: 0, y: 15, scale: 0.95 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        transition={{ type: "spring", damping: 20, stiffness: 300 }}
                          className={cn(
                            "flex flex-col gap-1.5 max-w-[85%]",
                            msg.role === 'user' ? "self-end items-end" : "self-start items-start"
                          )}
                        >

                          <div
                            className={cn(
                              "px-4 py-2.5 rounded-[22px] text-[14px] leading-relaxed font-medium",
                              msg.role === 'user' 
                                ? "bg-zinc-900 text-white rounded-tr-[4px] border border-white/5" 
                                : "bg-white/5 text-white/90 rounded-tl-[4px] border border-white/10"
                            )}
                          >
                            {msg.role === 'assistant' ? renderMessageContent(msg.content) : msg.content}

                        </div>
                      </motion.div>
                  ))}
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Input Controls */}
        <div
          className={cn(
            "flex items-center gap-3 px-4 py-3 min-h-[64px]",
            history.length === 0 && "bg-black/95 backdrop-blur-xl border border-white/10 rounded-[26px] shadow-2xl"
          )}
        >
          {/* Logo and Pin */}
            <div className="flex items-center gap-2.5">
              <motion.button
                layoutId={logoLayoutId}
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                onClick={() => onToggleWidgets?.()}
                  onDoubleClick={(e) => {
                    e.stopPropagation();
                    onDoubleClickLogo?.();
                  }}
                  className="p-1.5 rounded-xl hover:bg-white/5 transition-colors"
                >
                  <motion.div
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
                </motion.button>
            <button
              onClick={() => !isProcessing && fileInputRef.current?.click()}
              className="p-2.5 rounded-2xl bg-white/5 hover:bg-white/10 transition-colors group"
            >
              <Paperclip className="w-4.5 h-4.5 text-white/50 group-hover:text-white transition-colors" />
            </button>
          </div>

          <input
            type="file"
            className="hidden"
            ref={fileInputRef}
            onChange={handleFileSelect}
            accept={accept}
          />

          {/* Text Area */}
          <div className="flex-1 relative flex items-center">
              <Textarea
                id={id}
                placeholder={isProcessing ? "Processing..." : placeholder}
                className={cn(
                  "bg-transparent w-full p-0 text-left border-none focus-visible:ring-0 focus-visible:ring-offset-0 focus-visible:outline-none",
                  "placeholder:text-white/20 font-medium text-white/90 text-[15px]",
                  "resize-none leading-relaxed min-h-[24px] overflow-hidden",
                  isProcessing && "opacity-50 cursor-wait"
                )}
              style={{ height: `${height}px` }}
              ref={textareaRef}
              value={isProcessing ? "" : inputValue}
              disabled={isProcessing}
              onFocus={() => setIsFocused(true)}
              onBlur={() => setIsFocused(false)}
              onChange={(e) => {
                setInputValue(e.target.value);
                adjustHeight();
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSubmit();
                }
              }}
            />
          </div>

          {/* Right Controls */}
          <div className="flex items-center gap-3">
            <VisualMemoryCircle />
            
            <button
              onClick={handleSubmit}
              disabled={isProcessing || (!inputValue && !selectedFile)}
              className={cn(
                "flex items-center justify-center h-10 w-10 rounded-2xl transition-all",
                (isProcessing || (!inputValue && !selectedFile)) 
                  ? "bg-white/5 text-white/10 cursor-not-allowed" 
                  : "bg-white/20 text-white hover:bg-white/30 active:scale-95"
              )}
              type="button"
            >
              <CornerRightUp className="w-5 h-5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
