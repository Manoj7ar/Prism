import { useState, useRef } from "react";

interface UseFileInputOptions {
    accept?: string;
    maxSize?: number;
}

export function useFileInput({ accept, maxSize }: UseFileInputOptions) {
    const [fileName, setFileName] = useState<string>("");
    const [error, setError] = useState<string>("");
    const fileInputRef = useRef<HTMLInputElement>(null);
    const [fileSize, setFileSize] = useState<number>(0);
    const [selectedFile, setSelectedFile] = useState<File | undefined>();

    const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        validateAndSetFile(file);
    };

    const isAcceptedType = (file: File) => {
        if (!accept) return true;
        const fileType = (file.type || "").toLowerCase();
        const parts = accept
            .split(",")
            .map((p) => p.trim().toLowerCase())
            .filter(Boolean);

        const ext = (() => {
            const idx = file.name.lastIndexOf(".");
            return idx >= 0 ? file.name.slice(idx).toLowerCase() : "";
        })();

        return parts.some((rule) => {
            if (rule.startsWith(".")) {
                return ext === rule;
            }
            if (rule.endsWith("/*")) {
                const prefix = rule.slice(0, -1);
                return fileType.startsWith(prefix);
            }
            return fileType === rule;
        });
    };

    const validateAndSetFile = (file: File | undefined) => {
        setError("");

        if (file) {
            if (maxSize && file.size > maxSize * 1024 * 1024) {
                setError(`File size must be less than ${maxSize}MB`);
                return;
            }

            if (!isAcceptedType(file)) {
                setError("Unsupported file type. Use PDF, DOC, DOCX, TXT, or image files.");
                return;
            }

            setFileSize(file.size);
            setFileName(file.name);
            setSelectedFile(file);
        }
    };

    const clearFile = () => {
        setFileName("");
        setError("");
        setFileSize(0);
        setSelectedFile(undefined);
        if (fileInputRef.current) {
            fileInputRef.current.value = "";
        }
    };

    return {
        fileName,
        error,
        fileInputRef,
        handleFileSelect,
        validateAndSetFile,
        clearFile,
        fileSize,
        selectedFile,
    };
}
