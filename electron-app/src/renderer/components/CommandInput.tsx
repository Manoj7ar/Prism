import React, { useState, useRef, useEffect } from 'react';
import { Send, Loader2, Mic, MicOff } from 'lucide-react';

interface CommandInputProps {
  onSubmit: (command: string) => void;
  isLoading?: boolean;
}

export default function CommandInput({ onSubmit, isLoading }: CommandInputProps) {
  const [command, setCommand] = useState('');
  const [isListening, setIsListening] = useState(false);
  const recognitionRef = useRef<any>(null);

  useEffect(() => {
    if (typeof window !== 'undefined' && ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window)) {
      const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
      recognitionRef.current = new SpeechRecognition();
      recognitionRef.current.continuous = false;
      recognitionRef.current.interimResults = true;
      recognitionRef.current.lang = 'en-US';

      recognitionRef.current.onresult = (event: any) => {
        let interimTranscript = '';
        let finalTranscript = '';

        for (let i = event.resultIndex; i < event.results.length; ++i) {
          const transcript = event.results[i][0].transcript;
          if (event.results[i].isFinal) {
            finalTranscript += transcript;
          } else {
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
          } else {
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

      recognitionRef.current.onerror = (event: any) => {
        console.error('Speech recognition error:', event.error);
        setIsListening(false);
      };
    }
  }, [onSubmit]);

    useEffect(() => {
      if (window.electron && window.electron.onToggleRecording) {
        window.electron.onToggleRecording(() => {
          toggleListening();
        });
      }
    }, []);

    const toggleListening = () => {

    if (isListening) {
      recognitionRef.current?.stop();
    } else {
      setCommand('');
      recognitionRef.current?.start();
      setIsListening(true);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (command.trim() && !isLoading) {
      onSubmit(command);
      setCommand('');
    }
  };

  return (
    <form onSubmit={handleSubmit} className="relative flex gap-2">
      <div className="relative flex-1">
        <input
          type="text"
          value={command}
          onChange={(e) => setCommand(e.target.value)}
            placeholder={isListening ? "Listening..." : "Ask Prism to do something..."}
          className={`w-full bg-slate-800 border ${isListening ? 'border-blue-500 shadow-[0_0_10px_rgba(59,130,246,0.5)]' : 'border-slate-700'} rounded-xl px-4 py-3 pr-12 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500/50 transition-all`}
          disabled={isLoading}
        />
        <button
          type="submit"
          disabled={isLoading || !command.trim()}
          className="absolute right-2 top-1/2 -translate-y-1/2 p-2 text-slate-400 hover:text-blue-400 disabled:opacity-50 disabled:hover:text-slate-400 transition-colors"
        >
          {isLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
        </button>
      </div>
      <button
        type="button"
        onClick={toggleListening}
        disabled={isLoading}
        className={`p-3 rounded-xl border transition-all ${
          isListening 
            ? 'bg-blue-600 border-blue-500 text-white animate-pulse' 
            : 'bg-slate-800 border-slate-700 text-slate-400 hover:text-blue-400 hover:border-slate-600'
        }`}
        title={isListening ? "Stop Listening" : "Start Voice Command"}
      >
        {isListening ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
      </button>
    </form>
  );
}
