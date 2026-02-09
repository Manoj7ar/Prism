"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.default = VoiceRecorder;
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = require("react");
const lucide_react_1 = require("lucide-react");
const framer_motion_1 = require("framer-motion");
function VoiceRecorder({ isRecording, onRecordingComplete, onRecordingStart, onRecordingStop }) {
    const [isProcessing, setIsProcessing] = (0, react_1.useState)(false);
    const mediaRecorderRef = (0, react_1.useRef)(null);
    const audioChunksRef = (0, react_1.useRef)([]);
    const startRecording = async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            const mediaRecorder = new MediaRecorder(stream);
            mediaRecorderRef.current = mediaRecorder;
            audioChunksRef.current = [];
            mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    audioChunksRef.current.push(event.data);
                }
            };
            mediaRecorder.onstop = async () => {
                const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
                await handleTranscribe(audioBlob);
                // Stop all tracks to release the microphone
                stream.getTracks().forEach(track => track.stop());
            };
            mediaRecorder.start();
            onRecordingStart();
        }
        catch (err) {
            console.error('Error accessing microphone:', err);
            alert('Could not access microphone. Please check permissions.');
        }
    };
    const stopRecording = () => {
        if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
            mediaRecorderRef.current.stop();
            onRecordingStop();
        }
    };
    const handleTranscribe = async (blob) => {
        setIsProcessing(true);
        try {
            const formData = new FormData();
            formData.append('file', blob, 'recording.webm');
            const response = await fetch('http://localhost:8000/transcribe', {
                method: 'POST',
                body: formData,
            });
            const data = await response.json();
            if (data.success) {
                onRecordingComplete(data.transcription);
            }
            else {
                console.error('Transcription failed:', data.error);
                onRecordingComplete("Error: Could not transcribe audio.");
            }
        }
        catch (err) {
            console.error('Error sending audio to backend:', err);
            onRecordingComplete("Error: Backend connection failed.");
        }
        finally {
            setIsProcessing(false);
        }
    };
    const handleToggle = () => {
        if (isRecording) {
            stopRecording();
        }
        else {
            startRecording();
        }
    };
    return ((0, jsx_runtime_1.jsxs)("div", { className: "flex flex-col items-center gap-4 py-4", children: [(0, jsx_runtime_1.jsxs)("div", { className: "relative", children: [(0, jsx_runtime_1.jsx)(framer_motion_1.AnimatePresence, { children: isRecording && ((0, jsx_runtime_1.jsx)(framer_motion_1.motion.div, { initial: { scale: 0.8, opacity: 0 }, animate: { scale: 1.5, opacity: 0.2 }, exit: { scale: 0.8, opacity: 0 }, transition: { repeat: Infinity, duration: 1.5 }, className: "absolute inset-0 bg-blue-500 rounded-full" })) }), (0, jsx_runtime_1.jsx)("button", { onClick: handleToggle, disabled: isProcessing, className: `relative z-10 p-6 rounded-full transition-all duration-300 ${isRecording
                            ? 'bg-red-500 text-white shadow-lg shadow-red-500/50'
                            : 'bg-blue-600 text-white hover:bg-blue-500 shadow-lg shadow-blue-600/30'} ${isProcessing ? 'opacity-50 cursor-not-allowed' : ''}`, children: isProcessing ? ((0, jsx_runtime_1.jsx)(lucide_react_1.Loader2, { className: "w-8 h-8 animate-spin" })) : isRecording ? ((0, jsx_runtime_1.jsx)(lucide_react_1.Square, { className: "w-8 h-8 fill-current" })) : ((0, jsx_runtime_1.jsx)(lucide_react_1.Mic, { className: "w-8 h-8" })) })] }), (0, jsx_runtime_1.jsx)("p", { className: "text-xs text-slate-400 font-medium text-center", children: isProcessing
                    ? 'Transcribing audio...'
                    : isRecording
                        ? 'Listening... Click to stop'
                        : 'Click microphone to speak' })] }));
}
