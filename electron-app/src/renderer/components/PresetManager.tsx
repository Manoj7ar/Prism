import React, { useState, useEffect } from "react";
import { Plus, Play, Trash2, Edit2, X, List, Save, ChevronRight, Loader2, Info, Sparkles } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "../lib/utils";

interface Preset {
  id: string;
  name: string;
  steps: string[];
}

interface PresetManagerProps {
  onClose: () => void,
  onRun: (preset: Preset) => void,
  isProcessing?: boolean
}

export default function PresetManager({ onClose, onRun, isProcessing }: PresetManagerProps) {
  const [presets, setPresets] = useState<Preset[]>([]);
  const [isAdding, setIsAdding] = useState(false);
  const [editingPreset, setEditingPreset] = useState<Preset | null>(null);
  const [name, setName] = useState("");
  const [steps, setSteps] = useState<string[]>([""]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadPresets();
  }, []);

  const loadPresets = async () => {
    if (window.electron) {
      const data = await window.electron.getPresets();
      setPresets(data || []);
      setIsLoading(false);
    }
  };

  const handleSave = async () => {
    if (!name.trim() || steps.filter(s => s.trim()).length === 0) return;

    const preset: Preset = {
      id: editingPreset?.id || Math.random().toString(36).substr(2, 9),
      name,
      steps: steps.filter(s => s.trim())
    };

    if (window.electron) {
      await window.electron.savePreset(preset);
      await loadPresets();
      resetForm();
    }
  };

  const handleDelete = async (id: string) => {
    if (window.electron) {
      await window.electron.deletePreset(id);
      await loadPresets();
    }
  };

  const resetForm = () => {
    setIsAdding(false);
    setEditingPreset(null);
    setName("");
    setSteps([""]);
  };

  const startEdit = (preset: Preset) => {
    setEditingPreset(preset);
    setName(preset.name);
    setSteps(preset.steps.length > 0 ? preset.steps : [""]);
    setIsAdding(true);
  };

  return (
    <motion.div 
      initial={{ opacity: 0, scale: 0.95, y: 10 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.95, y: 10 }}
      transition={{ type: "spring", damping: 25, stiffness: 300 }}
      className="flex flex-col h-full bg-zinc-950 rounded-3xl border border-white/10 overflow-hidden shadow-2xl"
    >
      <div className="flex items-center justify-between px-6 py-4 border-b border-white/5 bg-white/5">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-blue-500/10">
            <Sparkles className="w-4 h-4 text-blue-400" />
          </div>
          <h2 className="text-lg font-semibold text-white/90">Automations</h2>
        </div>
        <button 
          onClick={onClose}
          className="p-2 rounded-full hover:bg-white/10 text-white/40 hover:text-white transition-all"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto custom-scrollbar p-5">
        <AnimatePresence mode="wait">
          {isAdding ? (
            <motion.div 
              key="edit-form"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              className="flex flex-col gap-6"
            >
              <div className="space-y-2">
                <label className="text-[10px] font-bold text-white/30 uppercase tracking-[0.2em] ml-1">Workflow Label</label>
                <input 
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Weekly Report"
                  className="w-full bg-white/5 border border-white/10 rounded-2xl px-5 py-3 text-white placeholder:text-white/20 focus:outline-none focus:ring-2 focus:ring-blue-500/20 transition-all font-medium"
                />
              </div>

              <div className="space-y-3">
                <label className="text-[10px] font-bold text-white/30 uppercase tracking-[0.2em] ml-1">Instructions</label>
                <div className="space-y-2.5">
                  {steps.map((step, index) => (
                    <div key={index} className="flex gap-2 group">
                      <div className="flex-1 relative">
                        <div className="absolute left-4 top-1/2 -translate-y-1/2 w-6 h-6 rounded-full bg-blue-500/10 flex items-center justify-center text-[10px] font-bold text-blue-400 border border-blue-500/20">
                          {index + 1}
                        </div>
                        <input 
                          value={step}
                          onChange={(e) => {
                            const newSteps = [...steps];
                            newSteps[index] = e.target.value;
                            setSteps(newSteps);
                          }}
                          placeholder="Describe the action..."
                          className="w-full bg-white/5 border border-white/10 rounded-2xl pl-12 pr-4 py-3 text-[13px] text-white/90 placeholder:text-white/20 focus:outline-none focus:ring-2 focus:ring-blue-500/20 transition-all"
                        />
                      </div>
                      {steps.length > 1 && (
                        <button 
                          onClick={() => setSteps(steps.filter((_, i) => i !== index))}
                          className="p-3 rounded-2xl hover:bg-red-500/10 text-red-400 opacity-0 group-hover:opacity-100 transition-all"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  ))}
                </div>
                <button 
                  onClick={() => setSteps([...steps, ""])}
                  className="flex items-center gap-2 text-[11px] text-blue-400 hover:text-blue-300 font-bold ml-1 transition-colors py-2 px-3 rounded-lg hover:bg-blue-500/5 w-fit"
                >
                  <Plus className="w-3.5 h-3.5" />
                  ADD STEP
                </button>
              </div>

              <div className="flex gap-3 pt-6 border-t border-white/5">
                <button 
                  onClick={resetForm}
                  className="flex-1 px-4 py-3 rounded-2xl bg-white/5 hover:bg-white/10 text-white/60 font-bold text-[13px] transition-all"
                >
                  CANCEL
                </button>
                <button 
                  onClick={handleSave}
                  disabled={!name.trim() || steps.every(s => !s.trim())}
                  className="flex-1 px-4 py-3 rounded-2xl bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-bold text-[13px] flex items-center justify-center gap-2 transition-all shadow-lg shadow-blue-900/20"
                >
                  <Save className="w-4 h-4" />
                  {editingPreset ? "UPDATE" : "SAVE"}
                </button>
              </div>
            </motion.div>
          ) : (
            <motion.div 
              key="list"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              className="space-y-4"
            >
              <button 
                onClick={() => setIsAdding(true)}
                className="w-full flex items-center justify-between px-6 py-5 rounded-[28px] bg-white/5 border border-dashed border-white/10 hover:border-blue-500/30 hover:bg-blue-500/5 transition-all group"
              >
                <div className="flex items-center gap-4">
                  <div className="p-2.5 rounded-2xl bg-blue-500/10 text-blue-400 group-hover:scale-110 transition-transform shadow-inner">
                    <Plus className="w-6 h-6" />
                  </div>
                  <div className="text-left">
                    <div className="font-bold text-white/90 text-[15px]">New Workflow</div>
                    <div className="text-[11px] text-white/30 font-medium">Create a multi-step automation</div>
                  </div>
                </div>
                <ChevronRight className="w-5 h-5 text-white/10 group-hover:text-blue-400 group-hover:translate-x-1 transition-all" />
              </button>

              {isLoading ? (
                <div className="flex flex-col items-center justify-center py-16 gap-3">
                  <Loader2 className="w-10 h-10 text-blue-500/40 animate-spin" />
                  <span className="text-[10px] font-bold text-white/20 uppercase tracking-[0.2em]">Synchronizing...</span>
                </div>
              ) : presets.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-16 text-center px-8">
                  <div className="w-20 h-20 rounded-full bg-white/[0.02] flex items-center justify-center mb-6 border border-white/5">
                    <List className="w-8 h-8 text-white/5" />
                  </div>
                  <div className="text-[13px] font-medium text-white/30 leading-relaxed italic">
                    "Automate the boring stuff. Create your first workflow above."
                  </div>
                </div>
              ) : (
                <div className="grid gap-3">
                  {presets.map((preset) => (
                    <motion.div 
                      key={preset.id}
                      layout
                      className="group relative flex items-center gap-4 p-5 rounded-[28px] bg-white/5 border border-white/5 hover:border-white/10 hover:bg-white/[0.08] transition-all"
                    >
                      <div className="flex-1 min-w-0">
                        <div className="font-bold text-white/90 text-[15px] truncate mb-1.5">{preset.name}</div>
                        <div className="flex items-center gap-2.5">
                          <span className="px-2 py-0.5 rounded-full bg-blue-500/10 text-[9px] font-black text-blue-400 border border-blue-500/10">
                            {preset.steps.length} {preset.steps.length === 1 ? 'STEP' : 'STEPS'}
                          </span>
                          <div className="text-[11px] text-white/20 truncate font-medium">
                            {preset.steps[0]}
                          </div>
                        </div>
                      </div>
                      
                      <div className="flex items-center gap-1.5 opacity-0 group-hover:opacity-100 transition-all translate-x-2 group-hover:translate-x-0">
                        <button 
                          onClick={() => startEdit(preset)}
                          className="p-2.5 rounded-xl hover:bg-white/10 text-white/30 hover:text-white transition-all"
                        >
                          <Edit2 className="w-4 h-4" />
                        </button>
                        <button 
                          onClick={() => handleDelete(preset.id)}
                          className="p-2.5 rounded-xl hover:bg-red-500/10 text-red-400 hover:text-red-300 transition-all"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                        <button 
                          onClick={() => onRun(preset)}
                          disabled={isProcessing}
                          className="ml-2 p-3 rounded-2xl bg-blue-600 text-white hover:bg-blue-500 disabled:opacity-50 disabled:cursor-wait transition-all active:scale-95 shadow-lg shadow-blue-900/30"
                        >
                          {isProcessing ? <Loader2 className="w-5 h-5 animate-spin" /> : <Play className="w-5 h-5 fill-current" />}
                        </button>
                      </div>
                    </motion.div>
                  ))}
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <div className="px-6 py-4 bg-white/[0.02] border-t border-white/5 flex items-center justify-between">
        <div className="flex items-center gap-2 text-white/20">
          <Info className="w-3 h-3" />
          <span className="text-[9px] font-bold uppercase tracking-widest">Tip: Use natural language for steps</span>
        </div>
        <p className="text-[9px] text-white/20 font-black uppercase tracking-[0.2em]">PRISM ENGINE</p>
      </div>
    </motion.div>
  );
}
