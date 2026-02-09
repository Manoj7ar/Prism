"use strict";
"use client";
Object.defineProperty(exports, "__esModule", { value: true });
exports.AIInput = AIInput;
const jsx_runtime_1 = require("react/jsx-runtime");
const lucide_react_1 = require("lucide-react");
const PrismIcon_1 = require("./PrismIcon");
const react_1 = require("react");
const utils_1 = require("../../lib/utils");
const textarea_1 = require("./textarea");
const use_auto_resize_textarea_1 = require("../../hooks/use-auto-resize-textarea");
const framer_motion_1 = require("framer-motion");
function AIInput({ id = "ai-input", placeholder = "Type your message...", minHeight = 52, maxHeight = 200, onSubmit, className, status }) {
    const { textareaRef, adjustHeight, height } = (0, use_auto_resize_textarea_1.useAutoResizeTextarea)({
        minHeight,
        maxHeight,
    });
    const [inputValue, setInputValue] = (0, react_1.useState)("");
    const handleReset = () => {
        if (!inputValue.trim())
            return;
        onSubmit?.(inputValue);
        setInputValue("");
        adjustHeight(true);
    };
    return ((0, jsx_runtime_1.jsx)("div", { className: (0, utils_1.cn)("w-full h-full flex items-center justify-center", className), children: (0, jsx_runtime_1.jsx)("div", { className: "relative w-full h-full", children: (0, jsx_runtime_1.jsx)(framer_motion_1.AnimatePresence, { mode: "wait", children: !status ? ((0, jsx_runtime_1.jsxs)(framer_motion_1.motion.div, { initial: { opacity: 0, scale: 0.95 }, animate: { opacity: 1, scale: 1 }, exit: { opacity: 0, scale: 0.95 }, transition: { duration: 0.2 }, className: "relative w-full", children: [(0, jsx_runtime_1.jsx)("div", { className: "flex flex-col gap-2", children: (0, jsx_runtime_1.jsx)(textarea_1.Textarea, { id: id, placeholder: placeholder, className: (0, utils_1.cn)("w-full bg-black/80 backdrop-blur-md rounded-3xl pl-6 pr-16", "placeholder:text-white/50", "border border-white/10 ring-white/10", "text-white text-wrap", "overflow-y-auto resize-none", "focus-visible:ring-1 focus-visible:ring-white/20 focus-visible:ring-offset-0", "transition-all duration-200 ease-out", "leading-[1.2] py-[16px]", "[&::-webkit-resizer]:hidden"), style: { height: `${height}px` }, ref: textareaRef, value: inputValue, onChange: (e) => {
                                    setInputValue(e.target.value);
                                    adjustHeight();
                                }, onKeyDown: (e) => {
                                    if (e.key === "Enter" && !e.shiftKey) {
                                        e.preventDefault();
                                        handleReset();
                                    }
                                } }) }), (0, jsx_runtime_1.jsx)("button", { onClick: handleReset, type: "button", className: (0, utils_1.cn)("absolute top-1/2 -translate-y-1/2 right-5", "rounded-xl bg-white/10 hover:bg-white/20 py-1.5 px-1.5", "transition-all duration-200", inputValue ? "opacity-100 scale-100" : "opacity-0 scale-90 pointer-events-none"), children: (0, jsx_runtime_1.jsx)(lucide_react_1.CornerRightUp, { className: "w-4 h-4 text-white" }) })] }, "input")) : ((0, jsx_runtime_1.jsx)(framer_motion_1.motion.div, { initial: { opacity: 0, scale: 0.8 }, animate: { opacity: 1, scale: 1 }, exit: { opacity: 0, scale: 0.8 }, className: "flex items-center justify-center w-full h-full", children: (0, jsx_runtime_1.jsx)("div", { className: "relative flex items-center justify-center w-12 h-12 rounded-full bg-white/10", children: (0, jsx_runtime_1.jsx)("div", { className: "flex items-center justify-center w-full h-full rounded-full", children: (0, jsx_runtime_1.jsx)(PrismIcon_1.PrismIcon, { className: "w-6 h-6 animate-pulse" }) }) }) }, "status")) }) }) }));
}
