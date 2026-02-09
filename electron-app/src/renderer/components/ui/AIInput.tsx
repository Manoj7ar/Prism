"use client";

import { CornerRightUp } from "lucide-react";
import { PrismIcon } from "./PrismIcon";
import { useState } from "react";
import { cn } from "../../lib/utils";
import { Textarea } from "./textarea";
import { useAutoResizeTextarea } from "../../hooks/use-auto-resize-textarea";
import { TextShimmer } from "./text-shimmer";
import { motion, AnimatePresence } from "framer-motion";

interface AIInputProps {
  id?: string
  placeholder?: string
  minHeight?: number
  maxHeight?: number
  onSubmit?: (value: string) => void
  className?: string
  status?: string
}

export function AIInput({
  id = "ai-input",
  placeholder = "Type your message...",
  minHeight = 52,
  maxHeight = 200,
  onSubmit,
  className,
  status
}: AIInputProps) {
    const { textareaRef, adjustHeight, height } = useAutoResizeTextarea({
      minHeight,
      maxHeight,
    });
  const [inputValue, setInputValue] = useState("");

  const handleReset = () => {
    if (!inputValue.trim()) return;
    onSubmit?.(inputValue);
    setInputValue("");
    adjustHeight(true);
  };

  return (
    <div className={cn("w-full h-full flex items-center justify-center", className)}>
      <div className="relative w-full h-full">
        <AnimatePresence mode="wait">
          {!status ? (
            <motion.div
              key="input"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              transition={{ duration: 0.2 }}
              className="relative w-full"
            >
              <div className="flex flex-col gap-2">
                <Textarea
                  id={id}
                  placeholder={placeholder}
                    className={cn(
                      "w-full bg-black/80 backdrop-blur-md rounded-3xl pl-6 pr-16",
                      "placeholder:text-white/50",
                      "border border-white/10 ring-white/10",
                      "text-white text-wrap",
                      "overflow-y-auto resize-none",
                      "focus-visible:ring-1 focus-visible:ring-white/20 focus-visible:ring-offset-0",
                      "transition-all duration-200 ease-out",
                      "leading-[1.2] py-[16px]",
                      "[&::-webkit-resizer]:hidden"
                    )}
                    style={{ height: `${height}px` }}
                    ref={textareaRef}
                    value={inputValue}
                  onChange={(e) => {
                    setInputValue(e.target.value);
                    adjustHeight();
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      handleReset();
                    }
                  }}
                />
              </div>

              <button
                onClick={handleReset}
                type="button"
                className={cn(
                  "absolute top-1/2 -translate-y-1/2 right-5",
                  "rounded-xl bg-white/10 hover:bg-white/20 py-1.5 px-1.5",
                  "transition-all duration-200",
                  inputValue ? "opacity-100 scale-100" : "opacity-0 scale-90 pointer-events-none"
                )}
              >
                <CornerRightUp className="w-4 h-4 text-white" />
              </button>
            </motion.div>
          ) : (
              <motion.div
                key="status"
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.8 }}
                className="flex items-center justify-center w-full h-full"
              >
                  <div className="relative flex items-center justify-center w-12 h-12 rounded-full bg-white/10">
                    <div className="flex items-center justify-center w-full h-full rounded-full">
                      <PrismIcon className="w-6 h-6 animate-pulse" />
                    </div>
                  </div>
              </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
