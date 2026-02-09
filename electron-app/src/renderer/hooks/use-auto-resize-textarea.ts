import { useEffect, useRef, useCallback, useState } from "react";

interface UseAutoResizeTextareaProps {
    minHeight: number;
    maxHeight?: number;
}

export function useAutoResizeTextarea({
    minHeight,
    maxHeight,
}: UseAutoResizeTextareaProps) {
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    const [height, setHeight] = useState(minHeight);

    const adjustHeight = useCallback(
        (reset?: boolean) => {
            const textarea = textareaRef.current;
            if (!textarea) return;

            if (reset) {
                setHeight(minHeight);
                return;
            }

            // Temporarily shrink to get the right scrollHeight
            const originalHeight = textarea.style.height;
            textarea.style.height = `${minHeight}px`;

            // Calculate new height
            const newHeight = Math.max(
                minHeight,
                Math.min(
                    textarea.scrollHeight,
                    maxHeight ?? Number.POSITIVE_INFINITY
                )
            );

            // Restore style so React can control it via height state
            textarea.style.height = originalHeight; 
            
            setHeight(newHeight);
        },
        [minHeight, maxHeight]
    );

    useEffect(() => {
        // Set initial height
        setHeight(minHeight);
    }, [minHeight]);

    // Adjust height on window resize
    useEffect(() => {
        const handleResize = () => adjustHeight();
        window.addEventListener("resize", handleResize);
        return () => window.removeEventListener("resize", handleResize);
    }, [adjustHeight]);

    return { textareaRef, adjustHeight, height };
}
