import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Key, Save, AlertCircle, Info, Lock } from 'lucide-react';

interface ApiKeyModalProps {
  isOpen: boolean;
  onSuccess: () => void;
}

const BACKEND_URL = "http://localhost:8000";

export default function ApiKeyModal({ isOpen, onSuccess }: ApiKeyModalProps) {
  const [key, setKey] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showInfo, setShowInfo] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!key.trim()) return;

    setIsLoading(true);
    setError(null);

    try {
      const res = await fetch(`${BACKEND_URL}/set-key`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key: key.trim() }),
      });

      const data = await res.json();

      if (data.success) {
        onSuccess();
      } else {
        setError(data.error || "Invalid API Key");
      }
    } catch (err) {
      setError("Failed to connect to backend");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 backdrop-blur-sm p-4"
        >
          <motion.div
            initial={{ scale: 0.95, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            className="w-full max-w-md bg-[#0f172a] border border-white/10 rounded-2xl shadow-2xl overflow-hidden"
          >
            <div className="p-6 border-b border-white/5 bg-gradient-to-r from-blue-500/10 to-purple-500/10">
              <div className="flex items-center gap-3 mb-2">
                <div className="p-2 rounded-lg bg-blue-500/20 text-blue-400">
                  <Key size={24} />
                </div>
                <h2 className="text-xl font-bold text-white">Enter API Key</h2>
              </div>
              <p className="text-white/60 text-sm">
                Prism requires a Google Gemini API Key to function.
              </p>
            </div>

            <div className="p-6 space-y-4">
              {error && (
                <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-200 text-sm flex items-center gap-2">
                  <AlertCircle size={16} />
                  <span>{error}</span>
                </div>
              )}

              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="space-y-2">
                  <label className="text-xs font-medium text-white/50 uppercase tracking-wider">
                    Gemini API Key
                  </label>
                  <div className="relative">
                    <input
                      type="password"
                      value={key}
                      onChange={(e) => setKey(e.target.value)}
                      placeholder="sk-..."
                      className="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-3 text-white placeholder:text-white/20 focus:outline-none focus:ring-2 focus:ring-blue-500/50 transition-all font-mono text-sm"
                      autoFocus
                    />
                    <Lock className="absolute right-3 top-3.5 text-white/20" size={16} />
                  </div>
                </div>

                <div className="flex items-center justify-between">
                  <button
                    type="button"
                    onClick={() => setShowInfo(!showInfo)}
                    className="text-white/40 hover:text-white/80 text-xs flex items-center gap-1.5 transition-colors"
                  >
                    <Info size={14} />
                    How is this stored?
                  </button>
                  <a 
                    href="https://aistudio.google.com/app/apikey" 
                    target="_blank" 
                    rel="noreferrer"
                    className="text-blue-400 hover:text-blue-300 text-xs transition-colors"
                  >
                    Get a key &rarr;
                  </a>
                </div>

                {showInfo && (
                   <motion.div 
                     initial={{ height: 0, opacity: 0 }}
                     animate={{ height: "auto", opacity: 1 }}
                     className="bg-white/5 rounded-lg p-3 text-xs text-white/60 leading-relaxed border border-white/5"
                   >
                     <strong>Privacy First:</strong> Your key is stored locally in a <code className="bg-black/30 px-1 py-0.5 rounded text-white/80">.env</code> file on your machine.
                   </motion.div>
                )}

                <button
                  type="submit"
                  disabled={isLoading || !key}
                  className="w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium py-3 rounded-xl transition-all flex items-center justify-center gap-2 shadow-lg shadow-blue-900/20"
                >
                  {isLoading ? (
                    <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  ) : (
                    <>
                      <Save size={18} />
                      Save & Continue
                    </>
                  )}
                </button>
              </form>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
