"use client";

import { CornerRightUp, Mic, CheckCircle2, Circle, Loader2, Waves } from "lucide-react";
import { useState, useEffect, useRef } from "react";
import { cn } from "@/lib/utils";
import { Textarea } from "@/components/ui/textarea";
import { useAutoResizeTextarea } from "@/hooks/use-auto-resize-textarea";
import { TextShimmer } from "@/components/ui/text-shimmer";
import { motion, AnimatePresence } from "framer-motion";

export interface Task {
  id: string;
  label: string;
  status: 'pending' | 'in_progress' | 'completed';
}

interface AIInputProps {
  id?: string
  placeholder?: string
  minHeight?: number
  maxHeight?: number
  onSubmit?: (value: string) => void
  onValueChange?: (value: string) => void
  className?: string
  status?: string
  tasks?: Task[]
}

export function AIInput({
  id = "ai-input",
  placeholder = "Type your message...",
  minHeight = 52,
  maxHeight = 200,
  onSubmit,
  onValueChange,
  className,
  status,
  tasks = [],
}: AIInputProps) {
    const { textareaRef, adjustHeight, height } = useAutoResizeTextarea({
      minHeight,
      maxHeight,
    });
  const [inputValue, setInputValue] = useState("");
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const handleReset = () => {
    if (!inputValue.trim()) return;
    onSubmit?.(inputValue);
    setInputValue("");
    adjustHeight(true);
  };

  return (
      <div className={cn("w-full py-4", className)}>
        <div className="relative max-w-2xl w-full mx-auto space-y-4">
          <AnimatePresence mode="popLayout">
          {tasks.length > 0 && (
            <motion.div 
              layout
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="flex flex-wrap gap-2 mb-4"
            >
              {tasks.map((task) => (
                <motion.div
                  key={task.id}
                  layout
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className={cn(
                    "flex items-center gap-2 px-3 py-1.5 rounded-xl border text-xs font-medium transition-colors duration-300 bg-black",
                    task.status === 'completed' 
                      ? "border-emerald-500/20 text-emerald-400" 
                      : task.status === 'in_progress'
                      ? "border-blue-500/20 text-blue-400"
                      : "border-zinc-700 text-zinc-400"
                  )}
                >
                  <AnimatePresence mode="wait">
                    {task.status === 'completed' && (
                      <motion.div
                        key="completed"
                        initial={{ scale: 0.5, opacity: 0 }}
                        animate={{ scale: 1, opacity: 1 }}
                      >
                        <CheckCircle2 className="w-3.5 h-3.5" />
                      </motion.div>
                    )}
                    {task.status === 'in_progress' && (
                      <motion.div
                        key="in_progress"
                        initial={{ scale: 0.5, opacity: 0 }}
                        animate={{ scale: 1, opacity: 1 }}
                      >
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      </motion.div>
                    )}
                    {task.status === 'pending' && (
                      <motion.div
                        key="pending"
                        initial={{ scale: 0.5, opacity: 0 }}
                        animate={{ scale: 1, opacity: 1 }}
                      >
                        <Circle className="w-3.5 h-3.5" />
                      </motion.div>
                    )}
                  </AnimatePresence>
                  <span>{task.label}</span>
                </motion.div>
              ))}
            </motion.div>
          )}
        </AnimatePresence>

        <div className="relative">
            <Textarea
              id={id}
              placeholder={placeholder}
              className={cn(
                "max-w-2xl bg-black rounded-3xl pl-6 pr-16",
              "placeholder:text-white/50",
              "border-none ring-white/10",
              "text-white text-wrap",
              "overflow-y-auto resize-none",
              "focus-visible:ring-0 focus-visible:ring-offset-0",
              "transition-all duration-300 ease-out",
              "leading-[1.2] py-[16px]",
              status && "opacity-10"
              )}
              style={{ height: `${height}px` }}
              ref={textareaRef}
              value={inputValue}
              onChange={(e) => {
                setInputValue(e.target.value);
                onValueChange?.(e.target.value);
                adjustHeight();
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleReset();
                }
              }}
              disabled={!!status}
            />

            <AnimatePresence>
              {status && (
                <motion.div 
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.95 }}
                  className="absolute inset-0 flex items-center justify-center pointer-events-none"
                >
                  <div className="bg-black/50 backdrop-blur-sm border border-white/10 px-4 py-2 rounded-2xl flex items-center gap-2">
                    <Loader2 className="w-4 h-4 text-white/50 animate-spin" />
                    <TextShimmer className="text-sm font-medium text-white">
                      {status}
                    </TextShimmer>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            <div
              className={cn(
                "absolute top-1/2 -translate-y-1/2 rounded-xl py-1 px-1 transition-all duration-300",
                inputValue ? "right-12" : "right-3",
                "bg-white/10"
              )}
            >
              <Mic className="w-4 h-4 text-white/70" />
            </div>
            
            <motion.button
              onClick={handleReset}
              type="button"
              initial={false}
              animate={{ 
                opacity: inputValue ? 1 : 0,
                scale: inputValue ? 1 : 0.9,
                right: 12
              }}
              className={cn(
                "absolute top-1/2 -translate-y-1/2",
                "rounded-xl bg-white/10 py-1 px-1",
                !inputValue && "pointer-events-none"
              )}
            >
              <CornerRightUp className="w-4 h-4 text-white/70" />
            </motion.button>
        </div>
      </div>
    </div>
  );
}
