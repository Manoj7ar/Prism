import React, { useState, useEffect } from 'react';
import { FileText, X } from 'lucide-react';

export default function SummaryView() {
  const [content, setContent] = useState<string>('Loading summary...');

  useEffect(() => {
    if (window.electron && window.electron.onUpdateSummary) {
      window.electron.onUpdateSummary((newContent: string) => {
        setContent(newContent);
      });
    }
  }, []);

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 p-8 flex flex-col gap-6">
      <header className="flex items-center justify-between border-b border-slate-800 pb-4">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-blue-500/10 rounded-lg">
            <FileText className="w-6 h-6 text-blue-400" />
          </div>
          <h1 className="text-xl font-bold">Task Summary</h1>
        </div>
      </header>

      <main className="flex-1 overflow-y-auto">
        <div className="prose prose-invert max-w-none">
          <p className="text-slate-300 leading-relaxed whitespace-pre-wrap">
            {content}
          </p>
        </div>
      </main>

      <footer className="text-xs text-slate-500 text-center border-t border-slate-800 pt-4">
        Press Esc to close this window
      </footer>
    </div>
  );
}
