"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.default = CommandInput;
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = require("react");
const lucide_react_1 = require("lucide-react");
function CommandInput({ onSubmit, isLoading }) {
    const [command, setCommand] = (0, react_1.useState)('');
    const [isListening, setIsListening] = (0, react_1.useState)(false);
    const recognitionRef = (0, react_1.useRef)(null);
    (0, react_1.useEffect)(() => {
        if (typeof window !== 'undefined' && ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window)) {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            recognitionRef.current = new SpeechRecognition();
            recognitionRef.current.continuous = false;
            recognitionRef.current.interimResults = true;
            recognitionRef.current.lang = 'en-US';
            recognitionRef.current.onresult = (event) => {
                let interimTranscript = '';
                let finalTranscript = '';
                for (let i = event.resultIndex; i < event.results.length; ++i) {
                    const transcript = event.results[i][0].transcript;
                    if (event.results[i].isFinal) {
                        finalTranscript += transcript;
                    }
                    else {
                        interimTranscript += transcript;
                    }
                }
                if (interimTranscript) {
                    setCommand(interimTranscript);
                }
                if (finalTranscript) {
                    const text = finalTranscript.toLowerCase().trim();
                    const wakeWord = 'hey prism';
                    if (text.includes(wakeWord)) {
                        const commandText = text.split(wakeWord).pop()?.trim();
                        if (commandText) {
                            setCommand(commandText);
                            onSubmit(commandText);
                            setCommand('');
                        }
                    }
                    else {
                        setCommand(finalTranscript);
                        // If we're not using wake word mode, just submit after a pause or if final
                        // For simplicity, we'll treat any final transcript as a command if wake word is not present
                        onSubmit(finalTranscript);
                        setCommand('');
                    }
                }
            };
            recognitionRef.current.onend = () => {
                setIsListening(false);
            };
            recognitionRef.current.onerror = (event) => {
                console.error('Speech recognition error:', event.error);
                setIsListening(false);
            };
        }
    }, [onSubmit]);
    (0, react_1.useEffect)(() => {
        if (window.electron && window.electron.onToggleRecording) {
            window.electron.onToggleRecording(() => {
                toggleListening();
            });
        }
    }, []);
    const toggleListening = () => {
        if (isListening) {
            recognitionRef.current?.stop();
        }
        else {
            setCommand('');
            recognitionRef.current?.start();
            setIsListening(true);
        }
    };
    const handleSubmit = (e) => {
        e.preventDefault();
        if (command.trim() && !isLoading) {
            onSubmit(command);
            setCommand('');
        }
    };
    return ((0, jsx_runtime_1.jsxs)("form", { onSubmit: handleSubmit, className: "relative flex gap-2", children: [(0, jsx_runtime_1.jsxs)("div", { className: "relative flex-1", children: [(0, jsx_runtime_1.jsx)("input", { type: "text", value: command, onChange: (e) => setCommand(e.target.value), placeholder: isListening ? "Listening..." : "Ask Prism to do something...", className: `w-full bg-slate-800 border ${isListening ? 'border-blue-500 shadow-[0_0_10px_rgba(59,130,246,0.5)]' : 'border-slate-700'} rounded-xl px-4 py-3 pr-12 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500/50 transition-all`, disabled: isLoading }), (0, jsx_runtime_1.jsx)("button", { type: "submit", disabled: isLoading || !command.trim(), className: "absolute right-2 top-1/2 -translate-y-1/2 p-2 text-slate-400 hover:text-blue-400 disabled:opacity-50 disabled:hover:text-slate-400 transition-colors", children: isLoading ? (0, jsx_runtime_1.jsx)(lucide_react_1.Loader2, { className: "w-5 h-5 animate-spin" }) : (0, jsx_runtime_1.jsx)(lucide_react_1.Send, { className: "w-5 h-5" }) })] }), (0, jsx_runtime_1.jsx)("button", { type: "button", onClick: toggleListening, disabled: isLoading, className: `p-3 rounded-xl border transition-all ${isListening
                    ? 'bg-blue-600 border-blue-500 text-white animate-pulse'
                    : 'bg-slate-800 border-slate-700 text-slate-400 hover:text-blue-400 hover:border-slate-600'}`, title: isListening ? "Stop Listening" : "Start Voice Command", children: isListening ? (0, jsx_runtime_1.jsx)(lucide_react_1.MicOff, { className: "w-5 h-5" }) : (0, jsx_runtime_1.jsx)(lucide_react_1.Mic, { className: "w-5 h-5" }) })] }));
}
