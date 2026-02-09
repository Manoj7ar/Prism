import React from 'react';
import { Files, Monitor, Clipboard, Globe, CheckCircle2, XCircle } from 'lucide-react';

interface StatusDisplayProps {
  context: any;
  results: any[];
}

export default function StatusDisplay({ context, results }: StatusDisplayProps) {
  return (
    <div className="flex-1 flex flex-col gap-4 overflow-hidden">
      {/* Context Panel */}
      <div className="grid grid-cols-2 gap-3">
        <div className="bg-slate-800/50 border border-slate-700/50 rounded-lg p-3">
          <div className="flex items-center gap-2 mb-2 text-blue-400">
            <Files className="w-4 h-4" />
            <span className="text-[10px] font-bold uppercase tracking-wider">Selected Files</span>
          </div>
          <div className="text-xs text-slate-300 truncate">
            {context?.selected_files?.length > 0 
              ? `${context.selected_files.length} files selected` 
              : 'No files selected'}
          </div>
        </div>
        
        <div className="bg-slate-800/50 border border-slate-700/50 rounded-lg p-3">
          <div className="flex items-center gap-2 mb-2 text-purple-400">
            <Monitor className="w-4 h-4" />
            <span className="text-[10px] font-bold uppercase tracking-wider">Active App</span>
          </div>
          <div className="text-xs text-slate-300 truncate">
            {context?.active_window || 'None detected'}
          </div>
        </div>
      </div>

      {/* Recent Activity */}
      <div className="flex-1 bg-slate-800/30 border border-slate-700/30 rounded-xl p-4 flex flex-col overflow-hidden">
        <h3 className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-4">Execution History</h3>
        <div className="flex-1 overflow-y-auto space-y-3 pr-2 scrollbar-hide">
          {results.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-slate-600 gap-2">
              <CheckCircle2 className="w-8 h-8 opacity-20" />
              <p className="text-xs italic">No recent activity</p>
            </div>
          ) : (
            results.map((res, i) => (
              <div key={i} className="bg-slate-800 border border-slate-700 rounded-lg p-3 animate-in fade-in slide-in-from-bottom-2">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[10px] font-semibold text-slate-400">{res.intent}</span>
                  {res.success ? (
                    <CheckCircle2 className="w-3 h-3 text-emerald-500" />
                  ) : (
                    <XCircle className="w-3 h-3 text-red-500" />
                  )}
                </div>
                <div className="space-y-1">
                  {res.tasks?.map((task: any, j: number) => (
                    <div key={j} className="text-[10px] text-slate-300 flex items-start gap-2">
                      <span className="text-slate-500">•</span>
                      <span>{task.description}</span>
                    </div>
                  ))}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
