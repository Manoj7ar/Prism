"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.useAutoResizeTextarea = useAutoResizeTextarea;
const react_1 = require("react");
function useAutoResizeTextarea({ minHeight, maxHeight, }) {
    const textareaRef = (0, react_1.useRef)(null);
    const [height, setHeight] = (0, react_1.useState)(minHeight);
    const adjustHeight = (0, react_1.useCallback)((reset) => {
        const textarea = textareaRef.current;
        if (!textarea)
            return;
        if (reset) {
            setHeight(minHeight);
            return;
        }
        // Temporarily shrink to get the right scrollHeight
        const originalHeight = textarea.style.height;
        textarea.style.height = `${minHeight}px`;
        // Calculate new height
        const newHeight = Math.max(minHeight, Math.min(textarea.scrollHeight, maxHeight ?? Number.POSITIVE_INFINITY));
        // Restore style so React can control it via height state
        textarea.style.height = originalHeight;
        setHeight(newHeight);
    }, [minHeight, maxHeight]);
    (0, react_1.useEffect)(() => {
        // Set initial height
        setHeight(minHeight);
    }, [minHeight]);
    // Adjust height on window resize
    (0, react_1.useEffect)(() => {
        const handleResize = () => adjustHeight();
        window.addEventListener("resize", handleResize);
        return () => window.removeEventListener("resize", handleResize);
    }, [adjustHeight]);
    return { textareaRef, adjustHeight, height };
}
